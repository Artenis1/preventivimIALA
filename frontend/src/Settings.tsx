import { useEffect, useState } from "react";
import { Plus, ShieldCheck, Sparkles, Save } from "lucide-react";
import { api, send } from "./api";
import { Field, ErrorBox, Loading } from "./ui";
export default function Settings() {
  const [settings, setSettings] = useState<any>(),
    [rates, setRates] = useState<Record<string, string>>({}),
    [rules, setRules] = useState<any[]>([]),
    [high, setHigh] = useState("0.93"),
    [medium, setMedium] = useState("0.65"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    api("/settings")
      .then((d) => {
        setSettings(d);
        setRates(d.exchange_rates || {});
        setRules(d.custom_unit_rules || []);
        setHigh(String(d.high_confidence));
        setMedium(String(d.medium_confidence));
      })
      .catch(setError);
  }, []);
  if (!settings) return error ? <ErrorBox error={error} /> : <Loading />;
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">KONFIGURIMI I PLATFORMËS</span>
          <h1>Cilësimet</h1>
          <p>Kurse këmbimi dhe rregulla të kontrolluara për llogarinë tuaj.</p>
        </div>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setSaved(false);
          setError(undefined);
          try {
            await send("/settings", "PUT", {
              exchange_rates: Object.fromEntries(
                Object.entries(rates).filter(([, v]) => v !== ""),
              ),
              custom_unit_rules: rules,
              high_confidence: Number(high),
              medium_confidence: Number(medium),
            });
            setSaved(true);
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <ErrorBox error={error} />
        {saved && (
          <div className="success">
            Cilësimet u ruajtën. Preventivat ekzistues nuk ndryshojnë
            automatikisht.
          </div>
        )}
        <div className="settings-grid">
          <section className="panel settings-section">
            <h2>Këmbimi valutor</h2>
            <p className="muted">
              Vendosni kursin për çdo drejtim. Sistemi nuk supozon kurs tregu
              apo kurs të anasjelltë.
            </p>
            <div className="form-grid">
              {[
                ["EUR:ALL", "1 EUR = ALL"],
                ["ALL:EUR", "1 ALL = EUR"],
              ].map(([key, label]) => (
                <Field key={key} label={label}>
                  <input
                    type="number"
                    min="0.000000001"
                    step="any"
                    placeholder="I pakonfiguruar"
                    value={rates[key] || ""}
                    onChange={(e) =>
                      setRates({ ...rates, [key]: e.target.value })
                    }
                  />
                </Field>
              ))}
            </div>
            <div className="notice">
              Kur kursi mungon, përputhjet me monedha të ndryshme kërkojnë
              zgjidhje manuale. Nuk bashkohen vlera në monedha të ndryshme.
            </div>
          </section>
          <section className="panel settings-section">
            <h2>
              <Sparkles size={19} />
              Përputhjet inteligjente
            </h2>
            <div className="ai-state">
              <span className={settings.ai_available ? "online" : "offline"} />
              {settings.ai_available
                ? "Ofruesi AI është konfiguruar"
                : "Ofruesi AI nuk është konfiguruar"}
            </div>
            <p className="muted">
              {settings.ai_available
                ? `Modeli: ${settings.ai_model} · Embeddings: ${settings.embedding_model}`
                : "Përputhja sipas kodit, tekstit dhe sinonimeve mbetet aktive. Çelësat AI konfigurohen vetëm në server."}
            </p>
            <div className="form-grid">
              <Field label="Pragu i besimit të lartë (0.80–1)">
                <input
                  required
                  type="number"
                  min="0.8"
                  max="1"
                  step="0.01"
                  value={high}
                  onChange={(e) => setHigh(e.target.value)}
                />
              </Field>
              <Field label="Pragu i mesëm (0.10–0.80)">
                <input
                  required
                  type="number"
                  min="0.1"
                  max="0.8"
                  step="0.01"
                  value={medium}
                  onChange={(e) => setMedium(e.target.value)}
                />
              </Field>
            </div>
            <p className="muted">
              Besimi nuk është garanci. Mospërputhjet teknike kërkojnë kontroll
              edhe kur teksti është i ngjashëm.
            </p>
          </section>
          <section className="panel settings-section full-span">
            <h2>Konvertime të personalizuara të njësive</h2>
            <p className="muted">
              Konvertimet fizike të njohura janë të integruara. Përdorni
              rregulla shtesë vetëm kur baza e sasisë është e dokumentuar.
              Miratimi është i detyrueshëm.
            </p>
            {rules.map((r, i) => (
              <div className="custom-rule" key={i}>
                <Field label="Nga njësia">
                  <input
                    required
                    value={r.source}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          i === j ? { ...x, source: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <Field label="Në njësinë">
                  <input
                    required
                    value={r.target}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          i === j ? { ...x, target: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <Field label="Faktori i sasisë">
                  <input
                    required
                    type="number"
                    min="0.000000001"
                    step="any"
                    value={r.factor}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          i === j ? { ...x, factor: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={r.approved}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          i === j ? { ...x, approved: e.target.checked } : x,
                        ),
                      )
                    }
                  />
                  Miratoj shprehimisht
                </label>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setRules(rules.filter((_, j) => i !== j))}
                >
                  Hiq
                </button>
              </div>
            ))}
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setRules([
                  ...rules,
                  { source: "", target: "", factor: "1", approved: false },
                ])
              }
            >
              <Plus size={15} />
              Shto rregull
            </button>
          </section>
          <section className="panel settings-section full-span privacy-section">
            <ShieldCheck size={24} />
            <div>
              <h2>Privatësia dhe shërbimet e jashtme</h2>
              <p>
                AI merr vetëm përshkrimin, njësinë dhe fushat teknike të
                nevojshme të rreshtit dhe kandidatëve. Skedarët e plotë Excel
                nuk dërgohen te ofruesi. Kur AI nuk përgjigjet, përputhjet bazë
                dhe puna manuale mbeten të disponueshme.
              </p>
              <small>
                Çelësat API ruhen në variabla mjedisi të backend-it. Mos
                vendosni kredenciale në shënime apo përshkrime.
              </small>
            </div>
          </section>
        </div>
        <div className="settings-footer">
          <button disabled={busy}>
            <Save size={16} />
            {busy ? "Duke ruajtur…" : "Ruaj cilësimet"}
          </button>
        </div>
      </form>
    </>
  );
}
