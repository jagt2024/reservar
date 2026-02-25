import { useState } from "react";
import { Download, Sparkles, Mail, Lock, CheckCircle, AlertCircle, Share2, Edit2, Save, X } from "lucide-react";

export default function PlanEstrategicoWeb() {
  const [step, setStep] = useState("auth");
  const [email, setEmail] = useState("");
  const [authCode, setAuthCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [sentCode, setSentCode] = useState("");

  const [businessName, setBusinessName] = useState("");
  const [businessDesc, setBusinessDesc] = useState("");
  const [generatedPlan, setGeneratedPlan] = useState(null);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [currentStepLabel, setCurrentStepLabel] = useState("");
  const [error, setError] = useState("");

  const [editingSection, setEditingSection] = useState(null);
  const [editedContent, setEditedContent] = useState("");

  const [shareUrl, setShareUrl] = useState("");
  const [showShareModal, setShowShareModal] = useState(false);

  const sendAuthCode = () => {
    if (!email || !email.includes("@")) {
      setError("Por favor ingresa un email válido");
      return;
    }
    const code = Math.floor(100000 + Math.random() * 900000).toString();
    setSentCode(code);
    setCodeSent(true);
    setError("");
    alert(`Código de verificación (simulado): ${code}\n\nEn producción, este código se enviaría por email.`);
  };

  const verifyCode = () => {
    if (authCode === sentCode) {
      setStep("form");
      setError("");
    } else {
      setError("Código incorrecto. Por favor intenta de nuevo.");
    }
  };

  const generateWithClaude = async (prompt) => {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 2048,
        messages: [{ role: "user", content: prompt }],
      }),
    });
    const data = await response.json();
    return data.content[0].text;
  };

  const getPromptForSection = (section, name, desc) => {
    const prompts = {
      "Resumen Ejecutivo": `Eres un consultor estratégico experto. Crea un Resumen Ejecutivo profesional para:
Nombre: ${name}
Descripción: ${desc}
Incluye: visión general, misión, visión a 5 años, 5 objetivos estratégicos con métricas, modelo de negocio resumido y KPIs principales. Mínimo 300 palabras.`,
      "Mercados Objetivo": `Eres un analista de mercado. Analiza los Mercados Objetivo Prioritarios para:
Nombre: ${name}
Descripción: ${desc}
Incluye: TAM-SAM-SOM, 4 segmentos prioritarios, estrategia de entrada, expansión geográfica. Mínimo 300 palabras.`,
      "Análisis Competitivo": `Eres un estratega competitivo. Crea un Análisis Competitivo para:
Nombre: ${name}
Descripción: ${desc}
Incluye: panorama competitivo, 5 Fuerzas de Porter aplicadas, oportunidades concretas y posicionamiento recomendado. Mínimo 300 palabras.`,
      "Propuesta de Valor": `Eres experto en branding. Define la Propuesta de Valor Única para:
Nombre: ${name}
Descripción: ${desc}
Incluye: declaración de valor central, 3 pilares de diferenciación, Value Proposition Canvas, estrategia de comunicación. Mínimo 300 palabras.`,
      "Plan de Acción": `Eres consultor de implementación estratégica. Crea un Plan de Acción para:
Nombre: ${name}
Descripción: ${desc}
Estructura en 3 fases (Meses 1-3, 4-12, 13-24) con objetivos, acciones, KPIs y recursos. Agrega 4 riesgos con mitigaciones y acciones para los próximos 30 días. Mínimo 400 palabras.`,
    };
    return prompts[section] || "";
  };

  const generatePlan = async () => {
    if (!businessName.trim() || !businessDesc.trim()) {
      setError("Por favor completa todos los campos");
      return;
    }
    if (businessDesc.trim().length < 30) {
      setError("La descripción debe tener al menos 30 caracteres");
      return;
    }

    setIsGenerating(true);
    setStep("generating");
    setError("");

    const sections = ["Resumen Ejecutivo", "Mercados Objetivo", "Análisis Competitivo", "Propuesta de Valor", "Plan de Acción"];
    const results = {};

    try {
      for (let i = 0; i < sections.length; i++) {
        const section = sections[i];
        setCurrentStepLabel(`Generando ${section}...`);
        setGenerationProgress(((i + 1) / sections.length) * 100);
        const prompt = getPromptForSection(section, businessName, businessDesc);
        results[section] = await generateWithClaude(prompt);
      }

      setGeneratedPlan({
        businessName,
        businessDesc,
        sections: results,
        createdAt: new Date().toISOString(),
        shareId: Math.random().toString(36).substring(7),
      });
      setStep("results");
    } catch (err) {
      setError("Error al generar el plan. Por favor intenta nuevamente.");
      setStep("form");
    } finally {
      setIsGenerating(false);
    }
  };

  const updateSection = (title, newContent) => {
    setGeneratedPlan((prev) => ({
      ...prev,
      sections: { ...prev.sections, [title]: newContent },
    }));
    setEditingSection(null);
  };

  const downloadHTML = () => {
    if (!generatedPlan) return;
    const html = `<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Plan Estratégico - ${generatedPlan.businessName}</title>
<style>body{font-family:'Segoe UI',sans-serif;line-height:1.7;color:#1e293b;max-width:800px;margin:0 auto;padding:40px 20px;}h1{color:#2563eb;border-bottom:3px solid #2563eb;padding-bottom:10px;margin-top:40px;}.cover{text-align:center;padding:60px 0;border-bottom:2px solid #2563eb;margin-bottom:40px;}.cover h1{font-size:2.5em;border:none;}</style>
</head><body>
<div class="cover"><h1>${generatedPlan.businessName}</h1><div>Plan de Negocio Estratégico</div><div style="margin-top:20px;color:#666;">${new Date(generatedPlan.createdAt).toLocaleDateString("es-ES")}</div></div>
${Object.entries(generatedPlan.sections).map(([title, content]) => `<div><h1>${title}</h1>${content.split("\n\n").map((p) => p.trim() ? `<p>${p}</p>` : "").join("")}</div>`).join("")}
</body></html>`;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `plan_${generatedPlan.businessName.replace(/\s+/g, "_")}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const sectionBadges = [
    { bg: "rgba(59,130,246,0.2)", border: "rgba(59,130,246,0.3)", text: "#93c5fd", icon: "📋" },
    { bg: "rgba(139,92,246,0.2)", border: "rgba(139,92,246,0.3)", text: "#c4b5fd", icon: "🎯" },
    { bg: "rgba(16,185,129,0.2)", border: "rgba(16,185,129,0.3)", text: "#6ee7b7", icon: "⚔️" },
    { bg: "rgba(245,158,11,0.2)", border: "rgba(245,158,11,0.3)", text: "#fcd34d", icon: "💡" },
    { bg: "rgba(244,63,94,0.2)", border: "rgba(244,63,94,0.3)", text: "#fda4af", icon: "🗺️" },
  ];

  const card = {
    background: "rgba(15,23,42,0.6)",
    backdropFilter: "blur(12px)",
    border: "1px solid rgba(148,163,184,0.1)",
    borderRadius: "16px",
  };

  const inputStyle = {
    background: "rgba(30,41,59,0.5)",
    border: "1.5px solid rgba(148,163,184,0.2)",
    color: "white",
    padding: "12px",
    borderRadius: "8px",
    width: "100%",
    fontSize: "14px",
    boxSizing: "border-box",
    marginBottom: "16px",
  };

  const btnPrimary = {
    background: "linear-gradient(135deg,#2563eb,#1d4ed8)",
    border: "none",
    color: "white",
    padding: "12px 24px",
    borderRadius: "8px",
    fontWeight: "600",
    cursor: "pointer",
    width: "100%",
    fontSize: "16px",
  };

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(135deg,#0f172a 0%,#1e3a8a 50%,#0f172a 100%)", color: "white", fontFamily: "system-ui,-apple-system,sans-serif" }}>
      <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "32px 16px" }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "48px" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "8px 16px", background: "rgba(37,99,235,0.2)", border: "1px solid rgba(37,99,235,0.3)", borderRadius: "20px", fontSize: "14px", fontWeight: "600", marginBottom: "16px" }}>
            <Sparkles size={16} />
            <span>Powered by Claude AI</span>
          </div>
          <h1 style={{ fontSize: "clamp(28px,5vw,48px)", fontWeight: "900", margin: "16px 0", background: "linear-gradient(to right,#93c5fd,#60a5fa)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
            Plan Estratégico de Negocio
          </h1>
          <p style={{ color: "#cbd5e1", fontSize: "18px" }}>Genera análisis estratégicos profesionales con IA</p>
        </div>

        {/* AUTH STEP */}
        {step === "auth" && (
          <div style={{ maxWidth: "480px", margin: "0 auto" }}>
            <div style={{ ...card, padding: "32px" }}>
              <div style={{ textAlign: "center", marginBottom: "24px" }}>
                <div style={{ width: "64px", height: "64px", background: "rgba(37,99,235,0.2)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
                  <Mail size={32} color="#60a5fa" />
                </div>
                <h2 style={{ fontSize: "24px", fontWeight: "bold", margin: "0 0 8px" }}>Acceso a la Plataforma</h2>
                <p style={{ color: "#94a3b8", fontSize: "14px", margin: 0 }}>Ingresa tu email para recibir un código de acceso</p>
              </div>

              {!codeSent ? (
                <>
                  <label style={{ display: "block", fontSize: "14px", fontWeight: "500", marginBottom: "8px" }}>Email</label>
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tu@email.com" onKeyPress={(e) => e.key === "Enter" && sendAuthCode()} style={inputStyle} />
                  {error && (
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "8px", color: "#fca5a5", fontSize: "14px", marginBottom: "16px" }}>
                      <AlertCircle size={16} /><span>{error}</span>
                    </div>
                  )}
                  <button onClick={sendAuthCode} style={btnPrimary}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}><Mail size={18} /><span>Enviar Código</span></div>
                  </button>
                </>
              ) : (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "12px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.3)", borderRadius: "8px", color: "#86efac", fontSize: "14px", marginBottom: "16px" }}>
                    <CheckCircle size={16} /><span>Código enviado a {email}</span>
                  </div>
                  <label style={{ display: "block", fontSize: "14px", fontWeight: "500", marginBottom: "8px" }}>Código de 6 dígitos</label>
                  <input type="text" value={authCode} onChange={(e) => setAuthCode(e.target.value)} placeholder="000000" maxLength={6} onKeyPress={(e) => e.key === "Enter" && verifyCode()} style={inputStyle} />
                  {error && (
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "8px", color: "#fca5a5", fontSize: "14px", marginBottom: "16px" }}>
                      <AlertCircle size={16} /><span>{error}</span>
                    </div>
                  )}
                  <button onClick={verifyCode} style={btnPrimary}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}><Lock size={18} /><span>Verificar Código</span></div>
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {/* FORM STEP */}
        {step === "form" && (
          <div style={{ maxWidth: "600px", margin: "0 auto" }}>
            <div style={{ ...card, padding: "32px" }}>
              <h2 style={{ fontSize: "24px", fontWeight: "bold", marginBottom: "8px" }}>Tu Negocio</h2>
              <p style={{ color: "#94a3b8", fontSize: "14px", marginBottom: "24px" }}>Cuéntanos sobre tu negocio y generaremos un plan estratégico completo</p>

              <label style={{ display: "block", fontSize: "14px", fontWeight: "500", marginBottom: "8px" }}>Nombre del Negocio</label>
              <input type="text" value={businessName} onChange={(e) => setBusinessName(e.target.value)} placeholder="Ej: TechStartup Colombia" style={inputStyle} />

              <label style={{ display: "block", fontSize: "14px", fontWeight: "500", marginBottom: "8px" }}>Descripción del Negocio</label>
              <textarea value={businessDesc} onChange={(e) => setBusinessDesc(e.target.value)} placeholder="Describe tu negocio: qué hace, a quién va dirigido, cuál es tu propuesta de valor, en qué etapa está..." rows={5} style={{ ...inputStyle, resize: "vertical" }} />
              <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "-12px", marginBottom: "16px" }}>{businessDesc.length}/30 mín. caracteres</div>

              {error && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "8px", color: "#fca5a5", fontSize: "14px", marginBottom: "16px" }}>
                  <AlertCircle size={16} /><span>{error}</span>
                </div>
              )}

              <button onClick={generatePlan} style={{ ...btnPrimary, background: "linear-gradient(135deg,#7c3aed,#6d28d9)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}><Sparkles size={18} /><span>Generar Plan Estratégico</span></div>
              </button>
            </div>
          </div>
        )}

        {/* GENERATING STEP */}
        {step === "generating" && (
          <div style={{ maxWidth: "500px", margin: "0 auto", textAlign: "center" }}>
            <div style={{ ...card, padding: "48px 32px" }}>
              <div style={{ width: "80px", height: "80px", background: "rgba(139,92,246,0.2)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px", animation: "pulse 2s infinite" }}>
                <Sparkles size={40} color="#a78bfa" />
              </div>
              <h2 style={{ fontSize: "24px", fontWeight: "bold", marginBottom: "8px" }}>Generando tu Plan</h2>
              <p style={{ color: "#94a3b8", marginBottom: "32px" }}>{currentStepLabel || "Iniciando..."}</p>
              <div style={{ background: "rgba(30,41,59,0.5)", borderRadius: "100px", height: "8px", overflow: "hidden", marginBottom: "8px" }}>
                <div style={{ height: "100%", background: "linear-gradient(90deg,#2563eb,#7c3aed)", borderRadius: "100px", width: `${generationProgress}%`, transition: "width 0.5s ease" }} />
              </div>
              <div style={{ fontSize: "14px", color: "#94a3b8" }}>{Math.round(generationProgress)}%</div>
            </div>
          </div>
        )}

        {/* RESULTS STEP */}
        {step === "results" && generatedPlan && (
          <div>
            {/* Results header */}
            <div style={{ ...card, padding: "24px 32px", marginBottom: "32px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "28px", fontWeight: "bold", marginBottom: "4px" }}>{generatedPlan.businessName}</h2>
                  <p style={{ color: "#94a3b8", margin: 0 }}>{new Date(generatedPlan.createdAt).toLocaleDateString("es-ES")}</p>
                </div>
                <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                  <button onClick={() => { setShareUrl(`https://tu-app.com/shared/${generatedPlan.shareId}`); setShowShareModal(true); }} style={{ padding: "12px 24px", borderRadius: "8px", fontWeight: "600", background: "linear-gradient(135deg,#8b5cf6,#7c3aed)", border: "none", color: "white", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Share2 size={18} /><span>Compartir</span>
                  </button>
                  <button onClick={downloadHTML} style={{ padding: "12px 24px", borderRadius: "8px", fontWeight: "600", background: "linear-gradient(135deg,#059669,#047857)", border: "none", color: "white", cursor: "pointer", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Download size={18} /><span>Descargar HTML</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Sections */}
            {Object.entries(generatedPlan.sections).map(([title, content], idx) => {
              const badge = sectionBadges[idx];
              const isEditing = editingSection === title;
              return (
                <div key={title} style={{ ...card, padding: "32px", marginBottom: "24px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                    <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", padding: "4px 12px", background: badge.bg, border: `1px solid ${badge.border}`, borderRadius: "20px", color: badge.text, fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "1px" }}>
                      <span>{badge.icon}</span><span>{title}</span>
                    </div>
                    {!isEditing ? (
                      <button onClick={() => { setEditingSection(title); setEditedContent(content); }} style={{ padding: "8px", background: "transparent", border: "none", cursor: "pointer", borderRadius: "8px" }}>
                        <Edit2 size={16} color="#94a3b8" />
                      </button>
                    ) : (
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button onClick={() => updateSection(title, editedContent)} style={{ padding: "8px", background: "#059669", border: "none", borderRadius: "8px", cursor: "pointer", color: "white" }}>
                          <Save size={16} />
                        </button>
                        <button onClick={() => { setEditingSection(null); setEditedContent(""); }} style={{ padding: "8px", background: "#dc2626", border: "none", borderRadius: "8px", cursor: "pointer", color: "white" }}>
                          <X size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                  <h3 style={{ fontSize: "22px", fontWeight: "bold", marginBottom: "16px" }}>{title}</h3>
                  {isEditing ? (
                    <textarea value={editedContent} onChange={(e) => setEditedContent(e.target.value)} style={{ ...inputStyle, minHeight: "300px", fontFamily: "inherit", fontSize: "14px", lineHeight: "1.7", resize: "vertical" }} />
                  ) : (
                    <div>
                      {content.split("\n\n").map((paragraph, i) => paragraph.trim() && (
                        <p key={i} style={{ color: "#cbd5e1", lineHeight: "1.7", marginBottom: "16px" }}>{paragraph}</p>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Share Modal */}
        {showShareModal && (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", padding: "16px", zIndex: 50 }}>
            <div style={{ ...card, padding: "32px", maxWidth: "500px", width: "100%" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
                <h3 style={{ fontSize: "22px", fontWeight: "bold", margin: 0 }}>Compartir Plan</h3>
                <button onClick={() => setShowShareModal(false)} style={{ padding: "8px", background: "transparent", border: "none", cursor: "pointer", borderRadius: "8px" }}>
                  <X size={20} color="#94a3b8" />
                </button>
              </div>
              <p style={{ color: "#cbd5e1", marginBottom: "16px" }}>Link para compartir tu plan:</p>
              <div style={{ display: "flex", gap: "8px" }}>
                <input type="text" value={shareUrl} readOnly style={{ ...inputStyle, margin: 0, flex: 1 }} />
                <button onClick={() => { navigator.clipboard.writeText(shareUrl); alert("¡Link copiado!"); }} style={{ padding: "12px 16px", background: "linear-gradient(135deg,#2563eb,#1d4ed8)", border: "none", color: "white", borderRadius: "8px", fontWeight: "600", cursor: "pointer", whiteSpace: "nowrap" }}>
                  Copiar
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
