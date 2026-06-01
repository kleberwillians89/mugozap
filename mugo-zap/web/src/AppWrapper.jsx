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

    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession || null);
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
      setSession(null);
    }
  }

  if (loading) {
    return (
      <div className="mwLoadingShell">
        <div className="mwLoadingCard">
          <div className="mwLoadingBrand">MUGÔ</div>
          <div className="mwLoadingText">Carregando painel interno...</div>
        </div>
      </div>
    );
  }

  if (!session) return <Login />;

  return (
    <div className="mwShell">
      <div className="mwTopActions">
        <button onClick={handleLogout} title="Sair" className="mwLogoutBtn">
          Sair
        </button>
      </div>

      <App />
    </div>
  );
}