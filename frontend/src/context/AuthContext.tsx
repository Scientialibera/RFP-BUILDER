/**
 * Authentication Context
 * Handles optional MSAL authentication based on backend config
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import { PublicClientApplication, AccountInfo, Configuration } from '@azure/msal-browser';
import { MsalProvider, useMsal } from '@azure/msal-react';
import { getConfig } from '../services/api';
import type { ConfigResponse } from '../types';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: AccountInfo | null;
  roles: string[];
  login: () => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (role?: string | null) => boolean;
  authEnabled: boolean;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  isLoading: true,
  user: null,
  roles: [],
  login: async () => {},
  logout: async () => {},
  hasRole: () => false,
  authEnabled: false,
});

export const useAuth = () => useContext(AuthContext);

// Inner provider that uses MSAL hooks
function MsalAuthProvider({ children, config }: { children: React.ReactNode; config: ConfigResponse }) {
  const { instance, accounts } = useMsal();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(false);
  }, [accounts]);

  const login = async () => {
    try {
      await instance.loginPopup({
        scopes: config.msal_scopes || ['User.Read'],
      });
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  const logout = async () => {
    try {
      await instance.logoutPopup();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const value: AuthContextType = {
    isAuthenticated: accounts.length > 0,
    isLoading,
    user: accounts[0] || null,
    roles: Array.isArray(accounts[0]?.idTokenClaims?.roles)
      ? (accounts[0]?.idTokenClaims?.roles as string[])
      : [],
    login,
    logout,
    hasRole: (role?: string | null) => {
      if (!role || !role.trim()) return true;
      const userRoles = Array.isArray(accounts[0]?.idTokenClaims?.roles)
        ? (accounts[0]?.idTokenClaims?.roles as string[])
        : [];
      return userRoles.includes(role.trim());
    },
    authEnabled: true,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// No-auth provider for when auth is disabled
function NoAuthProvider({ children }: { children: React.ReactNode }) {
  const value: AuthContextType = {
    isAuthenticated: true, // Always "authenticated" when auth is disabled
    isLoading: false,
    user: null,
    roles: [],
    login: async () => {},
    logout: async () => {},
    hasRole: () => true,
    authEnabled: false,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Main auth provider that determines which provider to use
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [msalInstance, setMsalInstance] = useState<PublicClientApplication | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function initAuth() {
      try {
        const configData = await getConfig();
        setConfig(configData);

        if (configData.auth_enabled && configData.msal_client_id && configData.msal_tenant_id) {
          const msalConfig: Configuration = {
            auth: {
              clientId: configData.msal_client_id,
              authority: `https://login.microsoftonline.com/${configData.msal_tenant_id}`,
              redirectUri: configData.msal_redirect_uri || window.location.origin,
            },
            cache: {
              cacheLocation: 'localStorage',
              storeAuthStateInCookie: false,
            },
          };

          const pca = new PublicClientApplication(msalConfig);
          await pca.initialize();
          setMsalInstance(pca);
        }
      } catch (err) {
        console.error('Failed to load config:', err);
        setError('Failed to load application configuration');
      } finally {
        setLoading(false);
      }
    }

    initAuth();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center text-red-600">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  // No auth enabled or no MSAL config
  if (!config?.auth_enabled || !msalInstance) {
    return <NoAuthProvider>{children}</NoAuthProvider>;
  }

  // Auth enabled with MSAL
  return (
    <MsalProvider instance={msalInstance}>
      <MsalAuthProvider config={config}>{children}</MsalAuthProvider>
    </MsalProvider>
  );
}
