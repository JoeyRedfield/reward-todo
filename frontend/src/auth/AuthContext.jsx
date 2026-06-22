import { createContext, useContext, useEffect, useRef, useState } from "react";
import {
  changePassword as changePasswordRequest,
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  setUnauthorizedHandler,
} from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const initializingRef = useRef(true);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      if (!initializingRef.current) {
        setSessionExpired(true);
      }
    });

    return () => {
      setUnauthorizedHandler(null);
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function initializeAuth() {
      try {
        const currentUser = await fetchCurrentUser();
        if (isMounted) {
          setUser(currentUser);
        }
      } catch {
        if (isMounted) {
          setUser(null);
        }
      } finally {
        initializingRef.current = false;
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    void initializeAuth();

    return () => {
      isMounted = false;
    };
  }, []);

  async function login(payload) {
    const currentUser = await loginRequest(payload);
    setUser(currentUser);
    setSessionExpired(false);
    return currentUser;
  }

  async function register(payload) {
    const currentUser = await registerRequest(payload);
    setUser(currentUser);
    setSessionExpired(false);
    return currentUser;
  }

  async function logout() {
    try {
      await logoutRequest();
    } finally {
      setUser(null);
      setSessionExpired(false);
    }
  }

  async function changePassword(payload) {
    const currentUser = await changePasswordRequest(payload);
    setUser(currentUser);
    setSessionExpired(false);
    return currentUser;
  }

  function clearSessionExpired() {
    setSessionExpired(false);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        sessionExpired,
        clearSessionExpired,
        login,
        register,
        logout,
        changePassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
