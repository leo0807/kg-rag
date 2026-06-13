"use client";

import { useState, useCallback, useEffect } from 'react';
import { fetchApi } from '@/lib/api';
import {
    addEdge, useNodesState, useEdgesState, useReactFlow, MarkerType,
} from '@xyflow/react';

export interface BuilderSchema { labels: string[]; relationship_types: string[]; }

export const EXAMPLES = [
    {
        title: "文档结构检索",
        desc: "查找规范下属的所有章节，了解文档大纲。",
        nodes: [
            { id: 'ex1_n1', type: 'schemaNode', position: { x: 100, y: 100 }, data: { label: 'Document' } },
            { id: 'ex1_n2', type: 'schemaNode', position: { x: 100, y: 300 }, data: { label: 'Section' } },
        ],
        edges: [
            { id: 'ex1_e1', source: 'ex1_n1', target: 'ex1_n2', label: 'HAS_SECTION', type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed } }
        ],
    },
    {
        title: "工艺资源配套",
        desc: "查询特定工序需要哪些工具支持，用于现场备料。",
        nodes: [
            { id: 'ex2_n1', type: 'schemaNode', position: { x: 100, y: 100 }, data: { label: 'Process' } },
            { id: 'ex2_n2', type: 'schemaNode', position: { x: 300, y: 100 }, data: { label: 'Tool' } },
        ],
        edges: [
            { id: 'ex2_e1', source: 'ex2_n1', target: 'ex2_n2', label: 'REQUIRES_TOOL', type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed } }
        ],
    },
    {
        title: "合规性冲突检查",
        desc: "识别哪些旧规范已被新版替代，防止误用过期标准。",
        nodes: [
            { id: 'ex3_n1', type: 'schemaNode', position: { x: 100, y: 100 }, data: { label: 'Document' } },
            { id: 'ex3_n2', type: 'schemaNode', position: { x: 350, y: 100 }, data: { label: 'Document' } },
        ],
        edges: [
            { id: 'ex3_e1', source: 'ex3_n1', target: 'ex3_n2', label: 'SUPERSEDES', type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed } }
        ],
    },
];

export function useBuilder() {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [schema, setSchema] = useState<BuilderSchema>({ labels: [], relationship_types: [] });
    const [cypher, setCypher] = useState('');
    const [results, setResults] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const [showTutorial, setShowTutorial] = useState(false);
    const { fitView } = useReactFlow();

    useEffect(() => {
        fetchApi<{ labels: string[]; relationship_types: string[] }>('/api/graph/schema').then(data => {
            setSchema({ labels: data.labels.filter((l: string) => !l.startsWith('_')), relationship_types: data.relationship_types });
        }).catch(() => {});
    }, []);

    useEffect(() => {
        if (!nodes.length) { setCypher(''); return; }
        const getVar = (id: string) => `v_${id.replace(/[^a-zA-Z0-9]/g, '_')}`;
        const clauses: string[] = [];
        nodes.forEach(n => clauses.push(`(${getVar(n.id)}:\`${n.data.label}\`)`));
        edges.forEach(e => {
            const s = nodes.find(n => n.id === e.source);
            const t = nodes.find(n => n.id === e.target);
            if (s && t) clauses.push(`(${getVar(s.id)})-[:\`${e.label || 'HAS'}\`]->(${getVar(t.id)})`);
        });
        setCypher(`MATCH ${clauses.join(',\n      ')}\nRETURN * LIMIT 25`);
    }, [nodes, edges]);

    const onConnect = useCallback((params: any) => {
        setEdges(eds => addEdge({
            ...params, type: 'smoothstep',
            markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1' },
            style: { stroke: '#6366f1', strokeWidth: 2 },
            label: 'HAS',
        }, eds));
    }, [setEdges]);

    const onEdgeClick = (_: any, edge: any) => {
        const next = prompt('输入关系类型 (例如: HAS_SECTION, REQUIRES_TOOL):', edge.label || 'HAS');
        if (next) setEdges(eds => eds.map(e => e.id === edge.id ? { ...e, label: next.toUpperCase() } : e));
    };

    const addNode = (label: string) => {
        const id = `node_${Math.random().toString(36).substr(2, 9)}`;
        setNodes(nds => nds.concat({ id, type: 'schemaNode', position: { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 }, data: { label } }));
    };

    const loadExample = (ex: typeof EXAMPLES[0]) => {
        setNodes(ex.nodes as any);
        setEdges(ex.edges as any);
        setShowTutorial(false);
        setTimeout(() => fitView({ duration: 800 }), 100);
    };

    const runQuery = async () => {
        setLoading(true); setError(null);
        try {
            const data = await fetchApi<{ error?: string; nodes?: unknown[]; edges?: unknown[] }>('/api/graph/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cypher }) });
            if (data.error) { setError(data.error); setResults(null); } else { setResults(data); }
        } catch (err: any) { setError(err.message || 'Network error'); }
        finally { setLoading(false); }
    };

    const copyToClipboard = () => {
        navigator.clipboard.writeText(cypher);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const clearCanvas = () => { setNodes([]); setEdges([]); setResults(null); setError(null); };

    return {
        nodes, edges, onNodesChange, onEdgesChange, onConnect, onEdgeClick,
        schema, cypher, results, loading, error, setError,
        copied, showTutorial, setShowTutorial,
        addNode, loadExample, runQuery, copyToClipboard, clearCanvas,
    };
}
