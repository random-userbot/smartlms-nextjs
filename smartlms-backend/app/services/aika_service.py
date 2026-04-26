import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_groq import ChatGroq
from langchain.tools.retriever import create_retriever_tool
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()

class AikaService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AikaService, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
        print("[AikaService] Initializing RAG Knowledge Base...")
        
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            print("[AikaService] ERROR: GROQ_API_KEY environment variable is missing.")
            self.agent_executor = None
            self.initialized = True
            return

        # 1. Setup Persistent Storage for AWS RDS (PGVector)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        db_url = os.environ.get("DATABASE_URL_SYNC", "postgresql://smartlms_admin:admin@localhost:5432/smartlms")
        
        # 2. Embeddings & VectorStore initialization
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # This will automatically initialize or connect to the pgvector extension and the 'aika_knowledge' collection
        self.vectorstore = PGVector(
            collection_name="aika_knowledge",
            connection_string=db_url,
            embedding_function=self.embeddings,
            use_jsonb=True
        )

        # (Optional Base Document Ingestion for totally empty DB)
        # We only ingest the base sample if DB collection doesn't exist or is empty
        try:
            doc_count = self.vectorstore.get().get("ids", [])
            is_empty = len(doc_count) == 0
        except Exception:
            is_empty = True

        if is_empty:
            self._ingest_base_document(base_dir)

        # 3. Retriever setup
        # We can pass search hooks to filter by user or role if needed in the future
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})

        # 4. LLM Initialization
        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.2
        )

        # 5. Agent & Tool Construction
        retriever_tool = create_retriever_tool(
            retriever,
            "search_course_materials",
            "Searches and returns chunks of documents uploaded by users or teachers. "
            "You MUST use this tool to answer any questions related to the course material, PDFs, docs, or SmartLMS.",
        )
        tools = [retriever_tool]

        system_prompt = (
            "You are Aika, a brilliant AI Tutor and assistant for SmartLMS. "
            "You can answer general educational questions from your own knowledge. "
            "However, if the user asks about course materials, PDFs, documents, or specific platform capabilities, you MUST use the `search_course_materials` tool. "
            "IMPORTANT: When you use information from the retrieved documents, you MUST cite your source clearly in your answer (e.g., 'According to [source_filename]...'). "
            "The retrieved documents will have metadata attached to them indicating their source."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, tools, prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        self.initialized = True
        print("[AikaService] RAG Persistent Agent online & Ready.")

    def _ingest_base_document(self, base_dir: str):
        file_path = os.path.join(base_dir, "scratch", "sample_knowledge.md")
        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# About Aika\nAika is an advanced AI assistant built using the Groq API.\n")
        
        self.ingest_document(file_path, metadata={"source": "sample_knowledge.md", "type": "system", "author": "admin"})

    def ingest_document(self, file_path: str, metadata: dict = None):
        """
        Dynamically ingests a new document (PDF, TXT, MD) into the persistent VectorDB.
        AWS Note: Call this function when a user uploads a file through the FastAPI router.
        """
        print(f"[AikaService] Ingesting document: {file_path}")
        if not os.path.exists(file_path):
             return False

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path, encoding='utf-8')
            
        docs = loader.load()

        # Overwrite metadata so LLM knows exactly what to cite
        if metadata:
            for doc in docs:
                doc.metadata.update(metadata)

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(docs)
        
        self.vectorstore.add_documents(splits)
        return True
            
        try:
            response = self.agent_executor.invoke({"input": question})
            return response["output"]
        except Exception as e:
            print(f"[AikaService] RAG Error: {e}")
            return "An internal error occurred while consulting the Aika Knowledge Base."

# Export singleton instance
aika_bot = AikaService()
