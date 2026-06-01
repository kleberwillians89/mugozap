import { useEffect, useState } from "react";
import { supabase } from "./lib/supabaseClient";
import App from "./App";
import Login from "./Login";

export default function Root() {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);

  useEffect(() => {
    let active = true;

    async function bootstrap() {
      try {
        const { data, error } = await supabase.auth.getSession();

        if (!active) return;

        if (error) {
          console.error("Erro ao carregar sessão:", error);
          setSession(null);
        } else {
          setSession(data?.session || null);
        }
      } catch (error) {
        if (!active) return;
        console.error("Falha ao resolver sessão inicial:", error);
        setSession(null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    bootstrap();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (!active) return;
      setSession(nextSession || null);
      setLoading(false);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#071b2c",
          color: "#fff",
          fontFamily: "Inter, sans-serif",
        }}
      >
        Carregando...
      </div>
    );
  }

  return session ? <App /> : <Login />;
}
