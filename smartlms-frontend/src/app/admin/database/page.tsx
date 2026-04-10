'use client';

import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Table as TableIcon, 
  ChevronRight, 
  ChevronLeft, 
  Search,
  Download,
  Terminal,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { adminAPI } from '@/lib/api';
import Sidebar from '@/components/Sidebar';

export default function DatabaseExplorerPage() {
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(true);

  useEffect(() => {
    loadTables();
  }, []);

  useEffect(() => {
    if (selectedTable) {
      loadTableData(selectedTable, 1);
    }
  }, [selectedTable]);

  const loadTables = async () => {
    setListLoading(true);
    try {
      const res = await adminAPI.getDBTables();
      setTables(res.data.tables);
      if (res.data.tables.length > 0 && !selectedTable) {
        setSelectedTable(res.data.tables[0]);
      }
    } catch (err) {
      console.error('Failed to load tables', err);
    } finally {
      setListLoading(false);
    }
  };

  const loadTableData = async (tableName: string, pageNum: number) => {
    setLoading(true);
    try {
      const res = await adminAPI.getTableData(tableName, pageNum);
      setData(res.data.rows);
      setTotal(res.data.total);
      setPage(res.data.page);
      
      if (res.data.rows.length > 0) {
        setColumns(Object.keys(res.data.rows[0]));
      } else {
        setColumns([]);
      }
    } catch (err) {
      console.error('Failed to load table data', err);
    } finally {
      setLoading(false);
    }
  };

  const renderCellValue = (value: any) => {
    if (value === null || value === undefined) {
      return <span className="text-text-muted italic text-xs">null</span>;
    }
    if (typeof value === 'object') {
      return (
        <button 
          onClick={() => console.log(value)}
          className="px-2 py-1 bg-primary/10 border border-primary/20 rounded text-[10px] text-primary font-bold uppercase"
        >
          View JSON
        </button>
      );
    }
    if (typeof value === 'boolean') {
      return (
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase ${value ? 'bg-success/20 text-success' : 'bg-error/20 text-error'}`}>
          {value ? 'True' : 'False'}
        </span>
      );
    }
    return <span className="truncate max-w-[200px] inline-block">{String(value)}</span>;
  };

  return (
    <div className="flex min-h-screen bg-background text-white selection:bg-primary/30">
      <Sidebar />
      
      <main className="flex-1 ml-64 flex flex-col h-screen overflow-hidden">
        {/* Top Header */}
        <header className="p-8 border-b border-white/5 bg-surface/30 backdrop-blur-md flex items-center justify-between shrink-0">
          <div>
            <div className="text-[10px] uppercase tracking-[0.3em] font-black text-primary mb-1">Infrastructure Awareness</div>
            <h1 className="text-4xl font-black tracking-tighter flex items-center gap-3">
              <Database className="text-primary" size={32} /> Live Matrix Explorer
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <button 
              onClick={() => selectedTable && loadTableData(selectedTable, page)}
              className="p-3 bg-white/5 border border-white/10 rounded-2xl hover:bg-primary/10 hover:border-primary/30 transition-all text-text-muted hover:text-primary"
            >
              <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Table List Sidebar */}
          <aside className="w-80 border-r border-white/5 bg-surface/20 overflow-y-auto p-4 space-y-2">
            <div className="px-4 py-2 text-[10px] font-black uppercase tracking-widest text-text-muted flex items-center justify-between">
              Database Cluster Tables
              {listLoading && <RefreshCw size={10} className="animate-spin text-primary" />}
            </div>
            
            {tables.map((table) => (
              <button
                key={table}
                onClick={() => setSelectedTable(table)}
                className={`w-full p-4 rounded-2xl flex items-center gap-4 transition-all group ${
                  selectedTable === table 
                    ? 'bg-primary text-background border-primary' 
                    : 'bg-white/5 border border-white/5 hover:border-primary/40'
                }`}
              >
                <TableIcon size={18} className={selectedTable === table ? 'text-background' : 'text-primary'} />
                <span className="flex-1 text-left font-bold text-sm tracking-tight">{table}</span>
                <ChevronRight size={16} className={selectedTable === table ? 'text-background/50' : 'text-white/10 group-hover:text-primary transition-all'} />
              </button>
            ))}
          </aside>

          {/* Table Data Grid */}
          <section className="flex-1 flex flex-col overflow-hidden bg-background">
            {!selectedTable ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-12 space-y-6">
                    <div className="w-24 h-24 bg-primary/10 rounded-[2.5rem] border border-primary/20 flex items-center justify-center text-primary animate-pulse">
                        <Terminal size={40} />
                    </div>
                    <div className="space-y-2">
                        <h2 className="text-2xl font-black">Waiting for node selection.</h2>
                        <p className="text-text-muted max-w-sm font-medium">Select a table from the cluster sidebar to reflect live Postgres records.</p>
                    </div>
                </div>
            ) : (
                <>
                  {/* Grid Toolbar */}
                  <div className="px-8 py-4 bg-surface/50 border-b border-white/5 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-6">
                        <div className="flex flex-col">
                            <span className="text-[10px] font-black text-primary uppercase tracking-widest leading-none mb-1">Live Reflection</span>
                            <span className="text-xl font-black tracking-tight">{selectedTable}</span>
                        </div>
                        <div className="h-8 w-px bg-white/10" />
                        <div className="flex flex-col">
                            <span className="text-[10px] font-black text-text-muted uppercase tracking-widest leading-none mb-1">Total Entries</span>
                            <span className="font-bold tracking-tight">{total.toLocaleString()}</span>
                        </div>
                    </div>
                    
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1">
                            <button 
                                onClick={() => loadTableData(selectedTable, page - 1)}
                                disabled={page === 1 || loading}
                                className="p-2 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
                            >
                                <ChevronLeft size={20} />
                            </button>
                            <div className="px-4 font-black text-xs uppercase tracking-widest">Page {page}</div>
                            <button 
                                onClick={() => loadTableData(selectedTable, page + 1)}
                                disabled={(page * 50) >= total || loading}
                                className="p-2 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 disabled:opacity-20 disabled:cursor-not-allowed transition-all"
                            >
                                <ChevronRight size={20} />
                            </button>
                        </div>
                    </div>
                  </div>

                  {/* Real Grid */}
                  <div className="flex-1 overflow-auto relative">
                    {loading && (
                        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-10 flex items-center justify-center">
                            <div className="flex flex-col items-center gap-4">
                                <RefreshCw className="text-primary animate-spin" size={32} />
                                <span className="text-[10px] font-black text-primary uppercase tracking-widest">Retrieving cluster bytes...</span>
                            </div>
                        </div>
                    )}

                    <table className="w-full border-collapse text-left">
                        <thead className="sticky top-0 bg-surface/80 backdrop-blur-md z-[5] border-b border-white/10">
                            <tr>
                                {columns.map(col => (
                                    <th key={col} className="px-6 py-4 text-[10px] font-black uppercase tracking-widest text-text-muted border-r border-white/5 min-w-[150px]">
                                        {col}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {data.length === 0 && !loading ? (
                                <tr>
                                    <td colSpan={columns.length} className="px-6 py-12 text-center">
                                        <div className="flex flex-col items-center gap-4 opacity-40">
                                            <AlertCircle size={32} />
                                            <span className="text-sm font-bold">Node is currently empty.</span>
                                        </div>
                                    </td>
                                </tr>
                            ) : (
                                data.map((row, i) => (
                                    <tr key={i} className="hover:bg-white/5 transition-colors group">
                                        {columns.map(col => (
                                            <td key={col} className="px-6 py-4 border-r border-white/5 text-sm font-medium text-white/80 group-hover:text-white">
                                                {renderCellValue(row[col])}
                                            </td>
                                        ))}
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                  </div>
                </>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
