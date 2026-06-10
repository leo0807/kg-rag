interface Step { label: string; done: boolean; active: boolean }

export function WizardStepper({ steps }: { steps: Step[] }) {
  return (
    <div className="flex items-center gap-0 mb-8">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium border-2 transition-colors ${
              step.done
                ? "bg-indigo-600 border-indigo-600 text-white"
                : step.active
                  ? "bg-gray-900 border-indigo-500 text-indigo-400"
                  : "bg-gray-900 border-gray-700 text-gray-600"
            }`}>
              {step.done ? "✓" : i + 1}
            </div>
            <span className={`mt-1 text-[10px] whitespace-nowrap ${
              step.active ? "text-indigo-400" : step.done ? "text-gray-400" : "text-gray-600"
            }`}>
              {step.label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className={`h-px w-12 mx-1 mb-4 transition-colors ${
              step.done ? "bg-indigo-600" : "bg-gray-800"
            }`} />
          )}
        </div>
      ))}
    </div>
  );
}
