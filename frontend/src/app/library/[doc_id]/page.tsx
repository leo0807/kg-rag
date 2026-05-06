import { Suspense } from "react";
import DocumentDetailClient from "./DocumentDetailClient";

type RouteParams = { doc_id: string };

export default async function DocumentDetailPage({ params }: { params: RouteParams | Promise<RouteParams> }) {
    const p = await params;
    return (
        <Suspense fallback={null}>
            <DocumentDetailClient docId={p.doc_id} />
        </Suspense>
    );
}
