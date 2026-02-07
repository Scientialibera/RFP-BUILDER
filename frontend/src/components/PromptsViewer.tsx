import type { PromptsResponse } from '../types';

interface PromptsViewerProps {
  prompts: PromptsResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

function PromptSection({ title, prompts }: { title: string; prompts: { name: string; content: string }[] }) {
  return (
    <section className="bg-white rounded-xl shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{title}</h2>
      <div className="space-y-3">
        {prompts.map((prompt) => (
          <details key={prompt.name} className="border border-gray-200 rounded-lg p-3">
            <summary className="cursor-pointer text-sm font-medium text-gray-800">{prompt.name}</summary>
            <pre className="mt-3 text-xs font-mono whitespace-pre-wrap break-words bg-gray-50 rounded p-3 max-h-[28rem] overflow-auto">
              {prompt.content}
            </pre>
          </details>
        ))}
      </div>
    </section>
  );
}

export function PromptsViewer({ prompts, loading, error, onRefresh }: PromptsViewerProps) {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Prompt Catalog</h2>
          <p className="text-sm text-gray-600">Read-only system and base prompts used by the backend.</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          Refresh
        </button>
      </div>

      {loading && (
        <div className="bg-white rounded-xl shadow-sm p-6 text-sm text-gray-600">
          Loading prompts...
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && prompts && (
        <>
          <PromptSection title="System Prompts" prompts={prompts.system_prompts} />
          <PromptSection title="Base Prompts" prompts={prompts.base_prompts} />
        </>
      )}
    </div>
  );
}

