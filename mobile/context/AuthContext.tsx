import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import Storage from "expo-sqlite/kv-store";
import { authApi, User } from "../services/resources";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: { name: string; email: string; password: string; phone?: string; village?: string; district?: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const token = await Storage.getItem("ww_token");
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await authApi.me();
        setUser(res.data);
      } catch {
        await Promise.all([Storage.removeItem("ww_token"), Storage.removeItem("ww_user")]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function login(email: string, password: string) {
    const res = await authApi.login(email, password);
    await Storage.setItem("ww_token", res.data.access_token);
    const me = await authApi.me();
    await Storage.setItem("ww_user", JSON.stringify(me.data));
    setUser(me.data);
    return me.data;
  }

  async function register(data: { name: string; email: string; password: string; phone?: string; village?: string; district?: string }) {
    await authApi.register(data);
    await login(data.email, data.password);
  }

  async function logout() {
    await Promise.all([Storage.removeItem("ww_token"), Storage.removeItem("ww_user")]);
    setUser(null);
  }

  async function refreshUser() {
    const res = await authApi.me();
    setUser(res.data);
    await Storage.setItem("ww_user", JSON.stringify(res.data));
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
