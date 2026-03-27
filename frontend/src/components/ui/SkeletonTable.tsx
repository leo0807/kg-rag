export default function SkeletonTable({ rows = 6 }: { rows?: number }) {
    return (
        <div className="p-8 max-w-4xl">
            <div className="h-8 w-48 bg-gray-800 rounded-lg mb-6 animate-pulse" />
            <div className="space-y-3">
                {Array.from({ length: rows }).map((_, i) => (
                    <div key={i} className="flex gap-4 py-3 border-b border-gray-800">
                        <div className="h-4 w-24 bg-gray-800 rounded animate-pulse" />
                        <div className="h-4 w-64 bg-gray-800 rounded animate-pulse" />
                        <div className="h-4 w-12 bg-gray-800 rounded animate-pulse" />
                        <div className="h-4 w-24 bg-gray-800 rounded animate-pulse" />
                        <div className="h-4 w-8  bg-gray-800 rounded animate-pulse" />
                    </div>
                ))}
            </div>
        </div>
    );
}