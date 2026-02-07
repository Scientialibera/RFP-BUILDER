/**
 * Progress indicator for workflow steps
 */

import { CheckCircle, Circle, Loader } from 'lucide-react';

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
    <div className="space-y-4">
      {steps.map((step, index) => {
        const isCompleted = completedSteps.includes(step.id);
        const isCurrent = currentStep === step.id;
        
        return (
          <div key={step.id} className="flex items-start">
            <div className="flex-shrink-0 mr-4">
              {isCompleted ? (
                <CheckCircle className="h-6 w-6 text-green-500" />
              ) : isCurrent ? (
                <Loader className="h-6 w-6 text-primary-500 animate-spin" />
              ) : (
                <Circle className="h-6 w-6 text-gray-300" />
              )}
            </div>
            <div className="flex-1">
              <p
                className={`text-sm font-medium ${
                  isCompleted
                    ? 'text-green-600'
                    : isCurrent
                    ? 'text-primary-600'
                    : 'text-gray-500'
                }`}
              >
                {step.name}
              </p>
              {step.description && (
                <p className="text-xs text-gray-500 mt-1">{step.description}</p>
              )}
            </div>
            {index < steps.length - 1 && (
              <div
                className={`absolute left-[11px] top-6 w-0.5 h-8 ${
                  isCompleted ? 'bg-green-500' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
