import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';
import type { PromptsResponse } from '../types';

type PromptGroup = 'system' | 'base';

interface PromptsViewerProps {
  prompts: PromptsResponse | null;
  loading: boolean;
  error: string | null;
  onSavePrompt: (promptGroup: PromptGroup, promptName: string, content: string) => Promise<void>;
  frontEndAuthEnabled: boolean;
  frontEndRequiredRole?: string;
  userRoles: string[];
  canModifyPrompts: boolean;
}

interface PromptSectionProps {
  title: string;
  promptGroup: PromptGroup;
  prompts: { name: string; content: string }[];
  drafts: Record<string, string>;
  setDrafts: Dispatch<SetStateAction<Record<string, string>>>;
  savingKey: string | null;
  saveError: string | null;
  saveErrorKey: string | null;
  saveSuccessKey: string | null;
  onSavePrompt: (promptGroup: PromptGroup, promptName: string, content: string) => Promise<void>;
  canModifyPrompts: boolean;
}

function promptKey(promptGroup: PromptGroup, promptName: string): string {
  return `${promptGroup}:${promptName}`;
}

function PromptSection({
  title,
  promptGroup,
  prompts,
  drafts,
  setDrafts,
  savingKey,
  saveError,
  saveErrorKey,
  saveSuccessKey,
  onSavePrompt,
  canModifyPrompts,
}: PromptSectionProps) {
  return (
    <section className="bg-white rounded-xl shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{title}</h2>
      <div className="space-y-4">
        {prompts.map((prompt) => {
          const key = promptKey(promptGroup, prompt.name);
          const draftValue = drafts[key] ?? prompt.content;
          const isDirty = draftValue !== prompt.content;
          const isSaving = savingKey === key;
          const showSaved = saveSuccessKey === key;

          return (
            <details key={prompt.name} className="border border-gray-200 rounded-lg p-3">
              <summary className="cursor-pointer text-sm font-medium text-gray-800">{prompt.name}</summary>
              <div className="mt-3 space-y-3">
                <textarea
                  value={draftValue}
                  readOnly={!canModifyPrompts}
                  onChange={(event) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [key]: event.target.value,
                    }))
                  }
                  className="w-full h-72 text-xs font-mono whitespace-pre rounded p-3 border border-gray-300 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 read-only:bg-gray-100 read-only:text-gray-700"
                />
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void onSavePrompt(promptGroup, prompt.name, draftValue)}
                    disabled={!canModifyPrompts || !isDirty || isSaving}
                    className="px-3 py-1.5 text-xs font-medium rounded border border-gray-300 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isSaving ? 'Saving...' : 'Save Prompt'}
                  </button>
                  {canModifyPrompts && isDirty && !isSaving && (
                    <button
                      type="button"
                      onClick={() =>
                        setDrafts((prev) => ({
                          ...prev,
                          [key]: prompt.content,
                        }))
                      }
                      className="px-3 py-1.5 text-xs font-medium rounded border border-gray-300 hover:bg-gray-100"
                    >
                      Reset
                    </button>
                  )}
                  {showSaved && <span className="text-xs text-green-700">Saved</span>}
                </div>
                {saveError && saveErrorKey === key && (
                  <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                    {saveError}
                  </div>
                )}
              </div>
            </details>
          );
        })}
      </div>
    </section>
  );
}

export function PromptsViewer({
  prompts,
  loading,
  error,
  onSavePrompt,
  frontEndAuthEnabled,
  frontEndRequiredRole,
  userRoles,
  canModifyPrompts,
}: PromptsViewerProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveErrorKey, setSaveErrorKey] = useState<string | null>(null);
  const [saveSuccessKey, setSaveSuccessKey] = useState<string | null>(null);

  useEffect(() => {
    if (!prompts) {
      setDrafts({});
      return;
    }

    const nextDrafts: Record<string, string> = {};
    for (const prompt of prompts.system_prompts) {
      nextDrafts[promptKey('system', prompt.name)] = prompt.content;
    }
    for (const prompt of prompts.base_prompts) {
      nextDrafts[promptKey('base', prompt.name)] = prompt.content;
    }
    setDrafts(nextDrafts);
    setSaveSuccessKey(null);
    setSaveError(null);
    setSaveErrorKey(null);
  }, [prompts]);

  useEffect(() => {
    if (!saveSuccessKey) {
      return;
    }
    const handle = window.setTimeout(() => setSaveSuccessKey(null), 2000);
    return () => window.clearTimeout(handle);
  }, [saveSuccessKey]);

  const authHint = useMemo(() => {
    if (!frontEndAuthEnabled) {
      return 'Prompt read/write access is open (front_end_auth=false).';
    }
    if (frontEndRequiredRole) {
      return `Prompt access requires role "${frontEndRequiredRole}" or admin_permission (front_end_auth=true).`;
    }
    return 'Prompt access requires admin_permission (front_end_auth=true).';
  }, [frontEndAuthEnabled, frontEndRequiredRole]);

  const handleSavePrompt = async (promptGroup: PromptGroup, promptName: string, content: string) => {
    const key = promptKey(promptGroup, promptName);
    setSavingKey(key);
    setSaveError(null);
    setSaveErrorKey(null);
    try {
      await onSavePrompt(promptGroup, promptName, content);
      setSaveSuccessKey(key);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save prompt';
      setSaveError(message);
      setSaveErrorKey(key);
      throw err;
    } finally {
      setSavingKey(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Prompt Catalog</h2>
          <p className="text-sm text-gray-600">System and base prompts used by the backend.</p>
        </div>

        {frontEndAuthEnabled && frontEndRequiredRole && (
          <div className="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded p-2">{authHint}</div>
        )}

        {frontEndAuthEnabled && frontEndRequiredRole && (
          <div className="text-xs text-gray-600 bg-blue-50 border border-blue-200 rounded p-2">
            <span className="font-medium">User roles:</span>{' '}
            {userRoles.length > 0 ? userRoles.join(', ') : 'none'}
          </div>
        )}

        {!canModifyPrompts && (
          <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
            You can view once authorized, but prompt editing is disabled until the required role/admin permission is provided.
          </div>
        )}

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
          <PromptSection
            title="System Prompts"
            promptGroup="system"
            prompts={prompts.system_prompts}
            drafts={drafts}
            setDrafts={setDrafts}
            savingKey={savingKey}
            saveError={saveError}
            saveErrorKey={saveErrorKey}
            saveSuccessKey={saveSuccessKey}
            onSavePrompt={handleSavePrompt}
            canModifyPrompts={canModifyPrompts}
          />
          <PromptSection
            title="Base Prompts"
            promptGroup="base"
            prompts={prompts.base_prompts}
            drafts={drafts}
            setDrafts={setDrafts}
            savingKey={savingKey}
            saveError={saveError}
            saveErrorKey={saveErrorKey}
            saveSuccessKey={saveSuccessKey}
            onSavePrompt={handleSavePrompt}
            canModifyPrompts={canModifyPrompts}
          />
        </>
      )}
    </div>
  );
}
