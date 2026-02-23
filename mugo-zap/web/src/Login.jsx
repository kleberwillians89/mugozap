import { useState } from "react";
import { supabase } from "./lib/supabaseClient";
import "./login.css";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    setLoading(false);

    if (error) {
      alert(error.message);
      return;
    }

    // NÃO precisa reload: AppWrapper já muda de tela quando a sessão entra
  }

  return (
    <div className="loginPage">
      <div className="loginCard">
        <div className="loginBrand">
          <div className="loginLogo">M</div>
          <div className="loginBrandText">
            <div className="loginTitle">MugôZap</div>
            <div className="loginSub">Acesso ao painel</div>
          </div>
        </div>

        <form className="loginForm" onSubmit={handleLogin}>
          <label className="loginLabel">
            Email
            <input
              className="loginInput"
              placeholder="seuemail@dominio.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </label>

          <label className="loginLabel">
            Senha
            <input
              className="loginInput"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>

          <button className="loginBtn" type="submit" disabled={loading}>
            {loading ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}