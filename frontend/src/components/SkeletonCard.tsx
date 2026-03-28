export default function SkeletonCard() {
    return (
        <div className="space-y-3 animate-pulse">
            <div className="p-5 bg-gray-900 rounded-xl border border-gray-800">
                <div className="h-3 w-16 bg-gray-700 rounded mb-4" />
                <div className="space-y-2">
                    <div className="h-3 bg-gray-700 rounded w-full" />
                    <div className="h-3 bg-gray-700 rounded w-5/6" />
                    <div className="h-3 bg-gray-700 rounded w-4/6" />
                    <div className="h-3 bg-gray-700 rounded w-full" />
                    <div className="h-3 bg-gray-700 rounded w-3/4" />
                </div>
            </div>
            <div className="h-3 w-16 bg-gray-700 rounded" />
            {[1, 2, 3].map(i => (
                <div
                    key={i}
                    className="flex items-center justify-between px-4 py-3
                     bg-gray-900 rounded-lg border border-gray-800"
                >
                    <div className="flex gap-3 flex-1">
                        <div className="h-3 w-24 bg-gray-700 rounded" />
                        <div className="h-3 w-32 bg-gray-700 rounded" />
                    </div>
                    <div className="h-3 w-8 bg-gray-700 rounded" />
                </div>
            ))}
        </div>
    );
}
