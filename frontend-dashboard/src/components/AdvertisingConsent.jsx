import { useEffect, useState } from "react";
import { chooseAdvertising, hasAdvertisingChoice, pageView } from "../services/metaAdvertising";
export default function AdvertisingConsent() {
  const [open, setOpen] = useState(() => !hasAdvertisingChoice());
  const [error, setError] = useState("");
  useEffect(() => { pageView(); }, []);
  const production = window.location.hostname === "solveris.ia.br";
  const preview = /^saas-fiscal-demo-[a-z0-9-]+-nexialistamentors-projects\.vercel\.app$/.test(window.location.hostname);
  if ((!production && !preview) || !/^\/mei\/?$/.test(window.location.pathname)) return null;
  const choose = accepted => {
    if (chooseAdvertising(accepted)) { setOpen(false); setError(""); }
    else setError("Não foi possível guardar a escolha. A medição permanece desativada.");
  };
  return <aside aria-label="Preferências de medição publicitária" style={{padding:"12px 20px",background:"#101d2d",color:"#fff",fontSize:"14px"}}>
    {!production && <p role="status">Prévia de teste: nenhum evento é enviado à Meta neste endereço.</p>}
    {open ? <>
      <p>Medição publicitária opcional: com a sua autorização, utilizamos o Pixel da Meta para medir visitas e compras do serviço SOLVERIS e melhorar os anúncios. A Meta recebe dados técnicos do navegador, cookies e os eventos autorizados. Não enviamos documentos nem parâmetros fiscais. Pode recusar e continuar a utilizar todos os serviços.</p>
      <p>A recusa não altera o consentimento necessário ao serviço fiscal. Pode rever esta escolha em “Preferências de publicidade”.</p>
      <button type="button" onClick={() => choose(true)}>Aceitar medição publicitária</button>{" "}
      <button type="button" onClick={() => choose(false)}>Recusar</button>
      {error && <p role="status">{error}</p>}
    </> : <button type="button" onClick={() => setOpen(true)}>Preferências de publicidade</button>}
  </aside>;
}
