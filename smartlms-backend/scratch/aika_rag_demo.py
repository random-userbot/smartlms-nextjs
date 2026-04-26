import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# Load environment variables (Assumes GROQ_API_KEY is natively exported or in a .env file)
load_dotenv()

def main():
    # Ensure the Groq API key is set
    if not os.environ.get("GROQ_API_KEY"):
        print("Please set your GROQ_API_KEY environment variable. e.g. os.environ['GROQ_API_KEY'] = 'gsk_...'")
        return

    print("1. Loading Markdown Document...")
    # Using a sample markdown file. You can point this to any .md file in your workspace!
    file_path = "sample_knowledge.md"
    
    # Create the sample file if it doesn't exist for the demo
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# About Aika\nAika is an advanced AI assistant built using the Groq API.\n\n## Capabilities\n- Lightning fast inference\n- Retrieval-Augmented Generation (RAG)\n- Markdown document parsing\n\n## Contact\nAika was developed by Revanth. For support, email revanthpuram003@gmail.com.")

    loader = TextLoader(file_path, encoding='utf-8')
    docs = loader.load()

    print("2. Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    splits = text_splitter.split_documents(docs)

    print("3. Generating embeddings and storing in Vector DB (Chroma)...")
    # Using HuggingFace's free local embeddings so you don't pay for OpenAI embeddings
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # This stores the vectors in memory. You can persist it by passing persist_directory="./chroma_db"
    vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    print("4. Initializing Groq LLM...")
    llm = ChatGroq(
        model="llama-3.1-8b-instant", # Using the latest active Llama 3.1 model
        temperature=0.2
    )

    print("5. Building RAG Chain...")
    system_prompt = (
        "You are Aika, an intelligent assistant. "
        "Use the following retrieved context to answer the user's question accurately. "
        "If the answer is not in the context, say 'I don't have enough information to answer that.'\n\n"
        "Context:\n{context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    print("\n--- RAG Pipeline Ready ---")
    
    while True:
        question = input("\nAsk Aika a question (or type 'quit' to exit): ")
        if question.lower() in ['quit', 'exit', 'q']:
            break
            
        print("Thinking...")
        # The chain will automatically embed the question, search ChromaDB, and pass context to Groq!
        response = rag_chain.invoke({"input": question})
        
        print("\nAika's Answer:")
        print(response["answer"])

if __name__ == "__main__":
    main()
