import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle, Download, Loader, MessageSquare, Wand2 } from 'lucide-react';
import { FileUpload } from './FileUpload';
import {
  critiqueRFP,
  extractReqs,
  generateCustomRFP,
  getDownloadUrl,
  planProposalWithContext,
} from '../services/api';
import type {
  CritiqueResult,
  GeneratedCodePackage,
  GeneratedCodeSnippet,
  PlannedSection,
  ProposalPlan,
  RFPAnalysis,
  RFPRequirement,
} from '../types';

interface CustomFlowProps {
  defaultEnablePlanner: boolean;
  defaultEnableCritiquer: boolean;
}

const CATEGORY_OPTIONS: RFPRequirement['category'][] = [
  'technical',
  'management',
  'cost',
  'experience',
  'compliance',
  'other',
];

const PRIORITY_OPTIONS: Array<RFPRequirement['priority']> = ['high', 'medium', 'low'];

function csvToList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function csvToNumberList(value: string): number[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .flatMap((item) => {
      const matches = item.match(/\d+/g);
      if (!matches) return [];
      return matches.map((match) => Number(match)).filter((num) => Number.isFinite(num) && num > 0);
    });
}

function listToCsv(value: string[] | undefined): string {
  return (value ?? []).join(', ');
}

function numberListToCsv(value: number[] | undefined): string {
  return (value ?? []).join(', ');
}

function buildStepComment(
  generationContext: string,
  regenerationComment: string,
  isRegeneration: boolean
): string | undefined {
  const parts: string[] = [];
  if (generationContext.trim()) {
    parts.push(`Generation Context:\n${generationContext.trim()}`);
  }
  if (isRegeneration && regenerationComment.trim()) {
    parts.push(`Regeneration Comment:\n${regenerationComment.trim()}`);
  }
  const combined = parts.join('\n\n').trim();
  return combined || undefined;
}

function base64ToObjectUrl(base64: string, contentType: string): string {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: contentType });
  return URL.createObjectURL(blob);
}

function defaultRequirement(index: number): RFPRequirement {
  return {
    id: `REQ-${String(index + 1).padStart(3, '0')}`,
    description: '',
    category: 'other',
    is_mandatory: false,
    priority: 'medium',
  };
}

function defaultSection(index: number): PlannedSection {
  return {
    title: `Section ${index + 1}`,
    summary: '',
    related_requirements: [],
    rfp_pages: [],
    suggested_diagrams: [],
    suggested_charts: [],
    suggested_tables: [],
  };
}

const EMPTY_CODE_PACKAGE: GeneratedCodePackage = {
  mermaid: [],
  tables: [],
  diagrams: [],
};

export function CustomFlow({
  defaultEnablePlanner,
  defaultEnableCritiquer,
}: CustomFlowProps) {
  const [rfpFile, setRfpFile] = useState<File[]>([]);
  const [exampleFiles, setExampleFiles] = useState<File[]>([]);
  const [contextFiles, setContextFiles] = useState<File[]>([]);
  const [companyContextText, setCompanyContextText] = useState('');

  const [enablePlanner, setEnablePlanner] = useState(defaultEnablePlanner);
  const [enableCritiquer, setEnableCritiquer] = useState(defaultEnableCritiquer);

  const [analysis, setAnalysis] = useState<RFPAnalysis | null>(null);
  const [plan, setPlan] = useState<ProposalPlan | null>(null);
  const [documentCode, setDocumentCode] = useState('');
  const [codePackage, setCodePackage] = useState<GeneratedCodePackage>(EMPTY_CODE_PACKAGE);
  const [critique, setCritique] = useState<CritiqueResult | null>(null);

  const [reqsGenerationContext, setReqsGenerationContext] = useState('');
  const [reqsRegenerationComment, setReqsRegenerationComment] = useState('');
  const [planGenerationContext, setPlanGenerationContext] = useState('');
  const [planRegenerationComment, setPlanRegenerationComment] = useState('');
  const [generateContextComment, setGenerateContextComment] = useState('');
  const [generateRegenerationComment, setGenerateRegenerationComment] = useState('');
  const [critiqueComment, setCritiqueComment] = useState('');

  const [docxObjectUrl, setDocxObjectUrl] = useState<string | null>(null);
  const [docxFilename, setDocxFilename] = useState('proposal.docx');
  const [docxDownloadUrl, setDocxDownloadUrl] = useState<string | null>(null);
  const [newKeyTheme, setNewKeyTheme] = useState('');

  const [loadingStep, setLoadingStep] = useState<'extract' | 'plan' | 'generate' | 'critique' | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (docxObjectUrl) {
        URL.revokeObjectURL(docxObjectUrl);
      }
    };
  }, [docxObjectUrl]);

  useEffect(() => {
    setEnablePlanner(defaultEnablePlanner);
  }, [defaultEnablePlanner]);

  useEffect(() => {
    setEnableCritiquer(defaultEnableCritiquer);
  }, [defaultEnableCritiquer]);

  const canExtract = rfpFile.length === 1 && loadingStep === null;
  const canPlan = Boolean(analysis) && loadingStep === null;
  const canGenerate = Boolean(analysis) && rfpFile.length === 1 && exampleFiles.length > 0 && loadingStep === null;
  const canCritique = Boolean(analysis && documentCode.trim()) && loadingStep === null;

  const planRequiredLabel = useMemo(
    () => (enablePlanner ? 'Planner enabled' : 'Planner disabled (direct requirements -> generation)'),
    [enablePlanner]
  );

  const handleExtractReqs = async () => {
    if (rfpFile.length === 0) return;
    setLoadingStep('extract');
    setError(null);
    try {
      const comment = buildStepComment(
        reqsGenerationContext,
        reqsRegenerationComment,
        Boolean(analysis)
      );
      const result = await extractReqs(
        rfpFile[0],
        contextFiles.length > 0 ? contextFiles : undefined,
        comment,
        analysis?.requirements
      );
      if (!result.analysis) {
        throw new Error(result.message || 'No requirements returned.');
      }
      setAnalysis(result.analysis);
      if (!enablePlanner) {
        setPlan(null);
      }
      setCritique(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to extract requirements');
    } finally {
      setLoadingStep(null);
    }
  };

  const handlePlan = async () => {
    if (!analysis) return;
    setLoadingStep('plan');
    setError(null);
    try {
      const comment = buildStepComment(
        planGenerationContext,
        planRegenerationComment,
        Boolean(plan)
      );
      const result = await planProposalWithContext({
        analysis,
        companyContextText: companyContextText.trim() || undefined,
        companyContextFiles: contextFiles.length > 0 ? contextFiles : undefined,
        comment,
        previousPlan: plan ?? undefined,
      });
      if (!result.plan) {
        throw new Error(result.message || 'No plan returned.');
      }
      setPlan(result.plan);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate plan');
    } finally {
      setLoadingStep(null);
    }
  };

  const handleGenerate = async () => {
    if (!analysis || rfpFile.length === 0 || exampleFiles.length === 0) return;
    setLoadingStep('generate');
    setError(null);
    try {
      const comment = buildStepComment(
        generateContextComment,
        generateRegenerationComment,
        Boolean(documentCode.trim())
      );
      const result = await generateCustomRFP({
        sourceRfp: rfpFile[0],
        exampleRfps: exampleFiles,
        companyContext: contextFiles.length > 0 ? contextFiles : undefined,
        analysis,
        plan: enablePlanner ? plan ?? undefined : undefined,
        comment,
        previousDocumentCode: documentCode.trim() || undefined,
      });
      setDocumentCode(result.document_code);
      setCodePackage(result.code_package ?? EMPTY_CODE_PACKAGE);
      setDocxFilename(result.docx_filename || 'proposal.docx');
      setDocxDownloadUrl(result.docx_download_url ?? null);
      if (docxObjectUrl) {
        URL.revokeObjectURL(docxObjectUrl);
      }
      setDocxObjectUrl(base64ToObjectUrl(result.docx_base64, result.docx_content_type));
      setCritique(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate RFP');
    } finally {
      setLoadingStep(null);
    }
  };

  const handleCritique = async () => {
    if (!analysis || !documentCode.trim()) return;
    setLoadingStep('critique');
    setError(null);
    try {
      const result = await critiqueRFP({
        analysis,
        document_code: documentCode,
        comment: critiqueComment.trim() || undefined,
      });
      setCritique(result.critique ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to critique RFP');
    } finally {
      setLoadingStep(null);
    }
  };

  const updateRequirement = (index: number, patch: Partial<RFPRequirement>) => {
    setAnalysis((prev) => {
      if (!prev) return prev;
      const nextRequirements = [...prev.requirements];
      nextRequirements[index] = { ...nextRequirements[index], ...patch };
      return { ...prev, requirements: nextRequirements };
    });
  };

  const removeRequirement = (index: number) => {
    setAnalysis((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        requirements: prev.requirements.filter((_, idx) => idx !== index),
      };
    });
  };

  const addRequirement = () => {
    setAnalysis((prev) => {
      const base = prev ?? { summary: '', requirements: [] };
      return {
        ...base,
        requirements: [...base.requirements, defaultRequirement(base.requirements.length)],
      };
    });
  };

  const updateSection = (index: number, patch: Partial<PlannedSection>) => {
    setPlan((prev) => {
      if (!prev) return prev;
      const nextSections = [...prev.sections];
      nextSections[index] = { ...nextSections[index], ...patch };
      return { ...prev, sections: nextSections };
    });
  };

  const removeSection = (index: number) => {
    setPlan((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        sections: prev.sections.filter((_, idx) => idx !== index),
      };
    });
  };

  const addSection = () => {
    setPlan((prev) => {
      const base = prev ?? {
        overview: '',
        sections: [],
        key_themes: [],
        win_strategy: '',
      };
      return {
        ...base,
        sections: [...base.sections, defaultSection(base.sections.length)],
      };
    });
  };

  const addKeyTheme = () => {
    const theme = newKeyTheme.trim();
    if (!theme) return;
    setPlan((prev) => {
      if (!prev) return prev;
      return { ...prev, key_themes: [...prev.key_themes, theme] };
    });
    setNewKeyTheme('');
  };

  const removeKeyTheme = (index: number) => {
    setPlan((prev) => {
      if (!prev) return prev;
      return { ...prev, key_themes: prev.key_themes.filter((_, idx) => idx !== index) };
    });
  };

  const renderCodePackageGroup = (
    title: string,
    snippets: GeneratedCodeSnippet[],
    emptyMessage: string
  ) => (
    <div className="border border-gray-200 rounded-lg p-3 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-gray-800">{title}</p>
        <p className="text-xs text-gray-500">{snippets.length} snippets</p>
      </div>
      {snippets.length === 0 ? (
        <p className="text-xs text-gray-500">{emptyMessage}</p>
      ) : (
        <div className="space-y-3 max-h-[24rem] overflow-y-auto pr-2">
          {snippets.map((snippet) => (
            <div key={snippet.snippet_id} className="space-y-1">
              <p className="text-xs font-medium text-gray-700">{snippet.title}</p>
              <textarea
                value={snippet.code}
                readOnly
                className="w-full border border-gray-300 rounded px-2 py-2 text-xs font-mono bg-gray-50"
                rows={10}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-6">
        <h2 className="text-lg font-semibold text-gray-900">Custom Flow Setup</h2>

        <FileUpload
          label="RFP Document"
          description="Source RFP to analyze and respond to"
          files={rfpFile}
          onFilesChange={setRfpFile}
          multiple={false}
          required
        />

        <FileUpload
          label="Example RFP Responses"
          description="Style and format references"
          files={exampleFiles}
          onFilesChange={setExampleFiles}
          multiple
          maxFiles={5}
          required
        />

        <FileUpload
          label="Company Context (Optional)"
          description="Capability docs and supporting context"
          files={contextFiles}
          onFilesChange={setContextFiles}
          multiple
          maxFiles={5}
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex items-center justify-between border border-gray-200 rounded-lg px-4 py-3">
            <div>
              <p className="text-sm font-medium text-gray-700">Planner step</p>
              <p className="text-xs text-gray-500">{planRequiredLabel}</p>
            </div>
            <button
              type="button"
              onClick={() => setEnablePlanner((value) => !value)}
              className={`relative inline-flex h-6 w-11 rounded-full transition-colors ${
                enablePlanner ? 'bg-primary-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
                  enablePlanner ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </label>

          <label className="flex items-center justify-between border border-gray-200 rounded-lg px-4 py-3">
            <div>
              <p className="text-sm font-medium text-gray-700">Critique step</p>
              <p className="text-xs text-gray-500">
                {enableCritiquer ? 'Critique enabled' : 'Critique disabled'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setEnableCritiquer((value) => !value)}
              className={`relative inline-flex h-6 w-11 rounded-full transition-colors ${
                enableCritiquer ? 'bg-blue-600' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
                  enableCritiquer ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </label>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 mr-3 flex-shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Step 1: Extract Requirements</h3>
          {analysis && <CheckCircle className="h-5 w-5 text-green-600" />}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Generation Context For Requirements
          </label>
          <textarea
            value={reqsGenerationContext}
            onChange={(e) => setReqsGenerationContext(e.target.value)}
            placeholder="Guidance for initial requirement extraction"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            rows={3}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Regeneration Comment
          </label>
          <textarea
            value={reqsRegenerationComment}
            onChange={(e) => setReqsRegenerationComment(e.target.value)}
            placeholder={
              analysis
                ? 'Extra instructions for requirement regeneration'
                : 'Available after first requirements generation'
            }
            disabled={!analysis}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
            rows={3}
          />
        </div>

        <button
          type="button"
          onClick={handleExtractReqs}
          disabled={!canExtract}
          className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg disabled:bg-gray-300"
        >
          {loadingStep === 'extract' ? <Loader className="h-4 w-4 mr-2 animate-spin" /> : <Wand2 className="h-4 w-4 mr-2" />}
          {analysis ? 'Regenerate Requirements' : 'Extract Requirements'}
        </button>

        {analysis && (
          <div className="space-y-3 border border-gray-200 rounded-lg p-4">
            <label className="block text-sm font-medium text-gray-700">Summary</label>
            <textarea
              value={analysis.summary}
              onChange={(e) => setAnalysis({ ...analysis, summary: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              rows={3}
            />

            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-3">
                <p className="text-sm font-medium text-gray-700">Requirements</p>
                <p className="text-xs text-gray-500">{analysis.requirements.length} total</p>
              </div>
              <button
                type="button"
                onClick={addRequirement}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                + Add requirement
              </button>
            </div>

            <div className="space-y-3 max-h-[34rem] overflow-y-auto pr-2">
              {analysis.requirements.map((req, idx) => (
                <div key={`${req.id}-${idx}`} className="border border-gray-200 rounded-lg p-3 space-y-2">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Requirement ID</label>
                      <input
                        value={req.id}
                        onChange={(e) => updateRequirement(idx, { id: e.target.value })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="REQ-001"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Category</label>
                      <select
                        value={req.category}
                        onChange={(e) => updateRequirement(idx, { category: e.target.value as RFPRequirement['category'] })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                      >
                        {CATEGORY_OPTIONS.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Priority</label>
                      <select
                        value={req.priority ?? 'medium'}
                        onChange={(e) => updateRequirement(idx, { priority: e.target.value as RFPRequirement['priority'] })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                      >
                        {PRIORITY_OPTIONS.map((priority) => (
                          <option key={priority} value={priority}>
                            {priority}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Mandatory</label>
                      <label className="flex items-center gap-2 text-sm text-gray-700 h-[34px]">
                        <input
                          type="checkbox"
                          checked={req.is_mandatory}
                          onChange={(e) => updateRequirement(idx, { is_mandatory: e.target.checked })}
                        />
                        Yes
                      </label>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Description</label>
                    <textarea
                      value={req.description}
                      onChange={(e) => updateRequirement(idx, { description: e.target.value })}
                      className="w-full border border-gray-300 rounded px-2 py-2 text-sm"
                      rows={2}
                      placeholder="Requirement description"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => removeRequirement(idx)}
                    className="text-xs text-red-600 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {enablePlanner && (
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Step 2: Plan</h3>
            {plan && <CheckCircle className="h-5 w-5 text-green-600" />}
          </div>

          <textarea
            value={companyContextText}
            onChange={(e) => setCompanyContextText(e.target.value)}
            placeholder="Optional additional context text for planning"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            rows={3}
          />

          {contextFiles.length > 0 ? (
            <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
              Uploaded context PDFs will be added to planning context
            </div>
          ) : (
            <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
              Upload context PDFs above if you want them included in planning
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Generation Context For Plan
            </label>
            <textarea
              value={planGenerationContext}
              onChange={(e) => setPlanGenerationContext(e.target.value)}
              placeholder="Guidance for initial planning run"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              rows={3}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Regeneration Comment
            </label>
            <textarea
              value={planRegenerationComment}
              onChange={(e) => setPlanRegenerationComment(e.target.value)}
              placeholder={plan ? 'Extra instructions for plan regeneration' : 'Available after first plan generation'}
              disabled={!plan}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
              rows={3}
            />
          </div>

          <button
            type="button"
            onClick={handlePlan}
            disabled={!canPlan}
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg disabled:bg-gray-300"
          >
            {loadingStep === 'plan' ? <Loader className="h-4 w-4 mr-2 animate-spin" /> : <Wand2 className="h-4 w-4 mr-2" />}
            {plan ? 'Regenerate Plan' : 'Generate Plan'}
          </button>

          {plan && (
            <div className="space-y-3 border border-gray-200 rounded-lg p-4">
              <label className="block text-sm font-medium text-gray-700">Overview</label>
              <textarea
                value={plan.overview}
                onChange={(e) => setPlan({ ...plan, overview: e.target.value })}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                rows={2}
              />

              <label className="block text-sm font-medium text-gray-700">Win Strategy</label>
              <textarea
                value={plan.win_strategy}
                onChange={(e) => setPlan({ ...plan, win_strategy: e.target.value })}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
                rows={2}
              />

              <label className="block text-sm font-medium text-gray-700">Key Themes</label>
              <div className="border border-gray-300 rounded px-3 py-3 bg-gray-50">
                {plan.key_themes.length > 0 ? (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {plan.key_themes.map((theme, idx) => (
                      <div
                        key={`${theme}-${idx}`}
                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-white border border-gray-300 text-sm text-gray-800"
                      >
                        <span>{theme}</span>
                        <button
                          type="button"
                          onClick={() => removeKeyTheme(idx)}
                          className="text-red-600 hover:text-red-700 text-xs"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-500 mb-3">No key themes yet.</p>
                )}
                <div className="flex gap-2">
                  <input
                    value={newKeyTheme}
                    onChange={(e) => setNewKeyTheme(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addKeyTheme();
                      }
                    }}
                    className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm bg-white"
                    placeholder="Add key theme"
                  />
                  <button
                    type="button"
                    onClick={addKeyTheme}
                    className="px-3 py-2 text-sm bg-primary-600 text-white rounded hover:bg-primary-700"
                  >
                    Add
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between mt-3">
                <p className="text-sm font-medium text-gray-700">Sections</p>
                <button
                  type="button"
                  onClick={addSection}
                  className="text-sm text-primary-600 hover:text-primary-700"
                >
                  + Add section
                </button>
              </div>

              <div className="space-y-3 max-h-[34rem] overflow-y-auto pr-2">
                {plan.sections.map((section, idx) => (
                  <div key={`${section.title}-${idx}`} className="border border-gray-200 rounded-lg p-3 space-y-2">
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Section Title</label>
                      <input
                        value={section.title}
                        onChange={(e) => updateSection(idx, { title: e.target.value })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="Section title"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Section Summary</label>
                      <textarea
                        value={section.summary}
                        onChange={(e) => updateSection(idx, { summary: e.target.value })}
                        className="w-full border border-gray-300 rounded px-2 py-2 text-sm"
                        rows={2}
                        placeholder="Section summary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Related Requirement IDs</label>
                      <input
                        value={listToCsv(section.related_requirements)}
                        onChange={(e) => updateSection(idx, { related_requirements: csvToList(e.target.value) })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="REQ-001, REQ-002"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">RFP Page Numbers</label>
                      <input
                        value={numberListToCsv(section.rfp_pages)}
                        onChange={(e) => updateSection(idx, { rfp_pages: csvToNumberList(e.target.value) })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="1, 2, 15"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Suggested Diagrams</label>
                      <input
                        value={listToCsv(section.suggested_diagrams)}
                        onChange={(e) => updateSection(idx, { suggested_diagrams: csvToList(e.target.value) })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="flowchart, sequence"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Suggested Charts</label>
                      <input
                        value={listToCsv(section.suggested_charts)}
                        onChange={(e) => updateSection(idx, { suggested_charts: csvToList(e.target.value) })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="bar chart, burndown"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Suggested Tables</label>
                      <input
                        value={listToCsv(section.suggested_tables)}
                        onChange={(e) => updateSection(idx, { suggested_tables: csvToList(e.target.value) })}
                        className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                        placeholder="compliance matrix, pricing table"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => removeSection(idx)}
                      className="text-xs text-red-600 hover:text-red-700"
                    >
                      Remove section
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">
            Step {enablePlanner ? '3' : '2'}: Generate RFP
          </h3>
          {(docxObjectUrl || docxDownloadUrl) && <CheckCircle className="h-5 w-5 text-green-600" />}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Generation Context For RFP Code
          </label>
          <textarea
            value={generateContextComment}
            onChange={(e) => setGenerateContextComment(e.target.value)}
            placeholder="Guidance for initial code generation"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            rows={3}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Regeneration Comment
          </label>
          <textarea
            value={generateRegenerationComment}
            onChange={(e) => setGenerateRegenerationComment(e.target.value)}
            placeholder={
              documentCode.trim()
                ? 'Extra instructions for regeneration'
                : 'Available after first document generation'
            }
            disabled={!documentCode.trim()}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
            rows={3}
          />
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={!canGenerate}
          className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg disabled:bg-gray-300"
        >
          {loadingStep === 'generate' ? <Loader className="h-4 w-4 mr-2 animate-spin" /> : <Wand2 className="h-4 w-4 mr-2" />}
          {documentCode ? 'Regenerate RFP' : 'Generate RFP'}
        </button>

        <div className="flex flex-wrap gap-3">
          {docxObjectUrl && (
            <a
              href={docxObjectUrl}
              download={docxFilename}
              className="inline-flex items-center px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
            >
              <Download className="h-4 w-4 mr-2" />
              Download DOCX (Local)
            </a>
          )}
          {docxDownloadUrl && (
            <a
              href={getDownloadUrl(docxDownloadUrl)}
              download
              className="inline-flex items-center px-4 py-2 border border-primary-300 text-primary-700 rounded-lg hover:bg-primary-50"
            >
              <Download className="h-4 w-4 mr-2" />
              Download DOCX (Server)
            </a>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Executed Document Code</label>
          <textarea
            value={documentCode}
            onChange={(e) => setDocumentCode(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-xs font-mono"
            rows={18}
            placeholder="Generated code appears here. You can edit it before critique or regeneration."
          />
        </div>

        <details className="border border-gray-200 rounded-lg p-4">
          <summary className="cursor-pointer text-sm font-medium text-gray-800">
            Generated Asset Code Package (Mermaid, Tables, Diagrams)
          </summary>
          <p className="text-xs text-gray-500 mt-3 mb-3">
            This package reflects the latest generated code and is split for easier review/copy/editing.
          </p>
          <div className="space-y-3">
            {renderCodePackageGroup(
              'Mermaid Code',
              codePackage.mermaid,
              'No Mermaid snippets were detected in this generation.'
            )}
            {renderCodePackageGroup(
              'Table Code',
              codePackage.tables,
              'No table snippets were detected in this generation.'
            )}
            {renderCodePackageGroup(
              'Diagram/Chart Code',
              codePackage.diagrams,
              'No diagram/chart snippets were detected in this generation.'
            )}
          </div>
        </details>
      </div>

      {enableCritiquer && (
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">
              Step {enablePlanner ? '4' : '3'}: Critique
            </h3>
            {critique && <CheckCircle className="h-5 w-5 text-green-600" />}
          </div>

          <textarea
            value={critiqueComment}
            onChange={(e) => setCritiqueComment(e.target.value)}
            placeholder="Optional comment to direct the critique"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            rows={3}
          />

          <button
            type="button"
            onClick={handleCritique}
            disabled={!canCritique}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg disabled:bg-gray-300"
          >
            {loadingStep === 'critique' ? (
              <Loader className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <MessageSquare className="h-4 w-4 mr-2" />
            )}
            Run Critique
          </button>

          {critique && (
            <div className="border border-gray-200 rounded-lg p-4 space-y-3">
              <div className="flex items-center gap-2">
                {critique.needs_revision ? (
                  <AlertCircle className="h-5 w-5 text-amber-600" />
                ) : (
                  <CheckCircle className="h-5 w-5 text-green-600" />
                )}
                <p className="font-medium text-gray-800">
                  {critique.needs_revision ? 'Revisions recommended' : 'No revisions required'}
                </p>
              </div>

              <div>
                <p className="text-sm font-medium text-gray-700">Critique</p>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{critique.critique}</p>
              </div>

              {critique.priority_fixes.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700">Priority Fixes</p>
                  <ul className="list-disc pl-5 text-sm text-gray-700">
                    {critique.priority_fixes.map((item, idx) => (
                      <li key={`${item}-${idx}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                type="button"
                onClick={() => setGenerateRegenerationComment(critique.critique)}
                className="text-sm text-primary-600 hover:text-primary-700"
              >
                Use critique as regeneration comment
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
