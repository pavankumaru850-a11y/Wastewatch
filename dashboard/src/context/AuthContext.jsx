import { createContext, useContext, useEffect, useState } from "react";
import { authApi } from "../services/resources";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("ww_user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("ww_token");
    if (!token) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then((res) => {
        setUser(res.data);
        localStorage.setItem("ww_user", JSON.stringify(res.data));
      })
      .catch(() => {
        localStorage.removeItem("ww_token");
        localStorage.removeItem("ww_user");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const res = await authApi.login(email, password);
    localStorage.setItem("ww_token", res.data.access_token);
    const me = await authApi.me();
    localStorage.setItem("ww_user", JSON.stringify(me.data));
    setUser(me.data);
    return me.data;
  }

  function logout() {
    localStorage.removeItem("ww_token");
    localStorage.removeItem("ww_user");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
