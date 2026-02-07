/**
 * Header Component
 */

import { FileText, LogOut, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function Header() {
  const { isAuthenticated, user, login, logout, authEnabled } = useAuth();

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center">
            <FileText className="h-8 w-8 text-primary-600" />
            <span className="ml-2 text-xl font-bold text-gray-900">
              RFP Builder
            </span>
          </div>

          {/* Auth */}
          {authEnabled && (
            <div className="flex items-center space-x-4">
              {isAuthenticated ? (
                <>
                  <div className="flex items-center text-sm text-gray-700">
                    <User className="h-4 w-4 mr-2" />
                    {user?.name || user?.username || 'User'}
                  </div>
                  <button
                    onClick={logout}
                    className="inline-flex items-center px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                  >
                    <LogOut className="h-4 w-4 mr-1" />
                    Sign Out
                  </button>
                </>
              ) : (
                <button
                  onClick={login}
                  className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
                >
                  Sign In
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
