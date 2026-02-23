// web/src/AppWrapper.jsx
import { useEffect, useState } from "react";
import { supabase } from "./lib/supabaseClient";
import Login from "./Login";
import App from "./App";

export default function AppWrapper() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session || null);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session || null);
      setLoading(false);
    });

    return () => {
      mounted = false;
      listener?.subscription?.unsubscribe?.();
    };
  }, []);

  async function handleLogout() {
    try {
      await supabase.auth.signOut();
    } catch (e) {
      console.warn("logout error:", e);
    } finally {
      // garante voltar pra tela de login imediatamente
      setSession(null);
    }
  }

  if (loading) return <div style={{ padding: 40 }}>Carregando...</div>;

  if (!session) return <Login />;

  return (
    <div style={{ height: "100vh" }}>
      {/* Topbar simples só com Sair (não mexe no layout do App) */}
      <div
        style={{
          position: "fixed",
          top: 12,
          right: 12,
          zIndex: 9999,
        }}
      >
        <button
          onClick={handleLogout}
          title="Sair"
          style={{
            border: "1px solid rgba(255,255,255,.12)",
            background: "rgba(0,0,0,.35)",
            color: "white",
            padding: "10px 12px",
            borderRadius: 12,
            cursor: "pointer",
            backdropFilter: "blur(8px)",
          }}
        >
          Sair
        </button>
      </div>

      <App />
    </div>
  );
}