/**
 * Sidebar Navigation Component
 */

import { FileText, Play, Layers, Clock, Settings, Lightbulb, HelpCircle, MessageSquare, LogOut, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export type NavTab = 'standard' | 'custom' | 'config' | 'runs';

interface HeaderProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export function Header({ activeTab, onTabChange }: HeaderProps) {
  const { isAuthenticated, user, login, logout, authEnabled } = useAuth();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-white border-r border-gray-200 flex flex-col z-30">
      {/* Company Logo + App Name */}
      <div className="px-5 py-4 border-b border-gray-100">
        <div className="flex justify-center mb-3">
          <img src="/argano-logo.png" alt="Argano" className="h-8 object-contain" />
        </div>
        <div className="flex items-center">
          <div className="flex items-center justify-center h-8 w-8 bg-primary-500 rounded-lg">
            <FileText className="h-4 w-4 text-white" />
          </div>
          <div className="ml-2.5">
            <span className="text-base font-bold text-gray-900">RFP</span>
            <span className="text-base font-light text-gray-600 ml-1">Builder</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <button
          onClick={() => onTabChange('standard')}
          className={`sidebar-link w-full ${activeTab === 'standard' ? 'active' : 'text-gray-600'}`}
        >
          <Play className="h-[18px] w-[18px] mr-3 flex-shrink-0" />
          Standard Run
        </button>

        <button
          onClick={() => onTabChange('custom')}
          className={`sidebar-link w-full ${activeTab === 'custom' ? 'active' : 'text-gray-600'}`}
        >
          <Layers className="h-[18px] w-[18px] mr-3 flex-shrink-0" />
          Custom Run
        </button>

        <button
          onClick={() => onTabChange('config')}
          className={`sidebar-link w-full ${activeTab === 'config' ? 'active' : 'text-gray-600'}`}
        >
          <Settings className="h-[18px] w-[18px] mr-3 flex-shrink-0" />
          Config
        </button>

        <button
          onClick={() => onTabChange('runs')}
          className={`sidebar-link w-full ${activeTab === 'runs' ? 'active' : 'text-gray-600'}`}
        >
          <Clock className="h-[18px] w-[18px] mr-3 flex-shrink-0" />
          Last Runs
        </button>
      </nav>

      {/* Tips Section */}
      <div className="px-4 py-4 border-t border-gray-100">
        <div className="flex items-center mb-2">
          <Lightbulb className="h-4 w-4 text-primary-500 mr-2" />
          <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider">Tips for Best Results</span>
        </div>
        <ul className="space-y-1.5 text-xs text-gray-500">
          <li className="flex items-start">
            <span className="text-primary-400 mr-1.5 mt-0.5">&#8226;</span>
            Use high-quality example RFP responses
          </li>
          <li className="flex items-start">
            <span className="text-primary-400 mr-1.5 mt-0.5">&#8226;</span>
            Include company capability documents
          </li>
          <li className="flex items-start">
            <span className="text-primary-400 mr-1.5 mt-0.5">&#8226;</span>
            Ensure PDFs are text-searchable
          </li>
        </ul>
      </div>

      {/* Auth & Footer */}
      <div className="px-4 py-3 border-t border-gray-100">
        {authEnabled && isAuthenticated ? (
          <div className="space-y-2">
            <div className="flex items-center text-xs text-gray-600">
              <User className="h-3.5 w-3.5 mr-2" />
              <span className="truncate">{user?.name || user?.username || 'User'}</span>
            </div>
            <button
              onClick={logout}
              className="flex items-center text-xs text-gray-500 hover:text-gray-700 transition-colors"
            >
              <LogOut className="h-3.5 w-3.5 mr-2" />
              Sign Out
            </button>
          </div>
        ) : authEnabled ? (
          <button
            onClick={login}
            className="w-full px-3 py-2 bg-primary-500 text-white text-xs font-medium rounded-lg hover:bg-primary-600 transition-colors"
          >
            Sign In
          </button>
        ) : null}
        <div className="flex items-center gap-3 mt-3 text-xs text-gray-400">
          <span className="flex items-center hover:text-gray-600 transition-colors cursor-pointer">
            <HelpCircle className="h-3.5 w-3.5 mr-1" />
            Help
          </span>
          <span>|</span>
          <span className="flex items-center hover:text-gray-600 transition-colors cursor-pointer">
            <MessageSquare className="h-3.5 w-3.5 mr-1" />
            Feedback
          </span>
        </div>
      </div>
    </aside>
  );
}
