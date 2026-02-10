/**
 * Progress indicator for workflow steps - Right panel status style
 */

import { CheckCircle2, Circle, Loader, Check } from 'lucide-react';

interface Step {
  id: string;
  name: string;
  description?: string;
}

interface ProgressStepsProps {
  steps: Step[];
  currentStep: string | null;
  completedSteps: string[];
}

export function ProgressSteps({ steps, currentStep, completedSteps }: ProgressStepsProps) {
  return (
    <div className="space-y-3">
      {steps.map((step) => {
        const isCompleted = completedSteps.includes(step.id);
        const isCurrent = currentStep === step.id;

        return (
          <div key={step.id} className="flex items-center justify-between">
            <div className="flex items-center min-w-0">
              <div className="flex-shrink-0 mr-3">
                {isCompleted ? (
                  <div className="h-5 w-5 rounded-full bg-green-500 flex items-center justify-center">
                    <Check className="h-3 w-3 text-white" />
                  </div>
                ) : isCurrent ? (
                  <Loader className="h-5 w-5 text-primary-500 animate-spin" />
                ) : (
                  <Circle className="h-5 w-5 text-gray-300" />
                )}
              </div>
              <span
                className={`text-sm ${
                  isCompleted
                    ? 'text-gray-700 font-medium'
                    : isCurrent
                    ? 'text-primary-600 font-medium'
                    : 'text-gray-400'
                }`}
              >
                {step.name}
              </span>
            </div>
            {/* Right side check indicator */}
            <div className="flex-shrink-0 ml-2">
              {isCompleted ? (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              ) : isCurrent ? (
                <div className="h-4 w-4 rounded-full border-2 border-primary-300 animate-pulse" />
              ) : (
                <Circle className="h-4 w-4 text-gray-200" />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
