"use client";

import { Component, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: string;
}

export default class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: "" };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error: error.message };
    }

    render() {
        if (this.state.hasError) {
            return this.props.fallback ?? (
                <div className="flex flex-col items-center justify-center h-64 gap-4">
                    <AlertTriangle size={32} className="text-red-400" />
                    <div className="text-center">
                        <div className="text-sm text-gray-300 mb-1">页面出现错误</div>
                        <div className="text-xs text-gray-500">{this.state.error}</div>
                    </div>
                    <button
                        onClick={() => this.setState({ hasError: false, error: "" })}
                        className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg
                       hover:bg-indigo-500"
                    >
                        重试
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}