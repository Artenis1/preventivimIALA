import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Database,
  Boxes,
  Wrench,
  FileUp,
  ScanSearch,
  FolderOpen,
  Calculator,
  History,
  Settings,
  LogOut,
  Menu,
  X,
  HardHat,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";
import { api, send } from "./api";
import { labels } from "./i18n";
import type { Page } from "./types";
import { ErrorBox, Field, Loading } from "./ui";
import Prices from "./Prices";
import Projects from "./Projects";
import Import from "./Import";
import Review from "./Review";
import Dashboard from "./Dashboard";
import SettingsPage from "./Settings";
import HistoryPage from "./History";
const nav = [
  { id: "dashboard", icon: LayoutDashboard },
  { id: "prices", icon: Database },
  { id: "materials", icon: Boxes },
  { id: "labor", icon: Wrench },
  { id: "import", icon: FileUp },
  { id: "review", icon: ScanSearch },
  { id: "projects", icon: FolderOpen },
  { id: "estimates", icon: Calculator },
  { id: "history", icon: History },
  { id: "settings", icon: Settings },
] as const;
export default function App() {
  const [user, setUser] = useState<any>(),
    [loading, setLoading] = useState(true),
    [page, setPage] = useState<Page>("dashboard"),
    [mobile, setMobile] = useState(false),
    [projectId, setProjectId] = useState<number | null>(null);
  useEffect(() => {
    api("/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);
  if (loading) return <Loading />;
  if (!user) return <Auth onLogin={setUser} />;
  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <HardHat size={23} />
          </div>
          <div>
            SmartEstimate<span>AI ENGINEERING PLATFORM</span>
          </div>
          <button
            aria-label="Mbyll menunë"
            className="mobile-only icon-button"
            onClick={() => setMobile(false)}
          >
            <X />
          </button>
        </div>
        <div className="workspace-label">HAPËSIRA E PUNËS</div>
        <nav>
          {nav.map((n) => (
            <button
              className={page === n.id ? "selected" : ""}
              key={n.id}
              onClick={() => {
                setPage(n.id);
                setMobile(false);
              }}
            >
              <n.icon size={19} />
              <span>{labels[n.id]}</span>
              {page === n.id && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="secure-note">
            <ShieldCheck size={18} />
            <span>
              Vendimet mbeten tuajat.
              <small>AI sugjeron. Inxhinieri miraton.</small>
            </span>
          </div>
          <button
            className="user-box"
            onClick={async () => {
              await send("/auth/logout", "POST");
              setPage("dashboard");
              setProjectId(null);
              setMobile(false);
              setUser(null);
            }}
            title="Dil nga llogaria"
          >
            <span className="avatar">
              {(user.display_name || user.email || "U")
                .slice(0, 2)
                .toUpperCase()}
            </span>
            <span>
              {user.display_name || "Llogaria ime"}
              <small>{user.email}</small>
            </span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      {mobile && (
        <div className="sidebar-scrim" onClick={() => setMobile(false)} />
      )}
      <main>
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-only"
              aria-label="Hap menunë"
              onClick={() => setMobile(true)}
            >
              <Menu />
            </button>
            <span>
              Hapësira e punës <ChevronRight size={14} /> <b>{labels[page]}</b>
            </span>
          </div>
          <span className="environment">
            <span />
            Sistem i sigurt · SQ
          </span>
        </header>
        <div className="content">
          {["prices", "materials", "labor"].includes(page) ? (
            <Prices key={page} mode={page} />
          ) : page === "dashboard" ? (
            <Dashboard onNavigate={setPage} />
          ) : page === "projects" ? (
            <Projects
              onOpen={(id) => {
                setProjectId(id);
                setPage("estimates");
              }}
            />
          ) : page === "import" ? (
            <Import
              projectId={projectId}
              onProject={setProjectId}
              onDone={(id) => {
                setProjectId(id);
                setPage("review");
              }}
            />
          ) : page === "review" || page === "estimates" ? (
            <Review
              key={page}
              mode={page}
              projectId={projectId}
              onProject={setProjectId}
              onNavigate={setPage}
            />
          ) : page === "settings" ? (
            <SettingsPage />
          ) : (
            <HistoryPage />
          )}
        </div>
        <div className="bottom-note">
          SmartEstimate AI <span>·</span> Kontroll teknik. Vendime të
          dokumentuara.
        </div>
      </main>
    </div>
  );
}
function Auth({ onLogin }: { onLogin: (u: any) => void }) {
  const [register, setRegister] = useState(false),
    [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [name, setName] = useState(""),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  return (
    <div className="auth-page">
      <div className="auth-story">
        <div className="brand">
          <div className="brand-mark">
            <HardHat size={28} />
          </div>
          <div>
            SmartEstimate<span>AI ENGINEERING PLATFORM</span>
          </div>
        </div>
        <div>
          <span className="eyebrow">NGA SASITË TE VENDIMET</span>
          <h1>
            Preventiva të sakta.
            <br />
            Kontroll në çdo zë.
          </h1>
          <p>
            Menaxhoni çmimet, përpunoni preventivat Excel dhe rishikoni
            përputhjet me ndihmën e AI.
          </p>
          <div className="auth-points">
            <span>
              01 <b>Një bazë e përbashkët çmimesh</b>
            </span>
            <span>
              02 <b>Analizë teknike para miratimit</b>
            </span>
            <span>
              03 <b>Llogaritje dhe histori transparente</b>
            </span>
          </div>
        </div>
        <small>NDËRTIM · INXHINIERI · ENERGJI FOTOVOLTAIKE</small>
      </div>
      <section className="auth-form">
        <div className="auth-card">
          <span className="eyebrow">MIRË SE VINI</span>
          <h2>{register ? "Krijo llogarinë" : "Hyni në hapësirën tuaj"}</h2>
          <p className="muted">
            {register
              ? "Filloni menaxhimin e projekteve tuaja."
              : "Vazhdoni punën me çmimet dhe preventivat."}
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError(undefined);
              try {
                await send(
                  register ? "/auth/register" : "/auth/login",
                  "POST",
                  {
                    email,
                    password,
                    ...(register ? { display_name: name } : {}),
                  },
                );
                onLogin(await api("/auth/me"));
              } catch (e) {
                setError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            {register && (
              <Field label="Emri i plotë">
                <input
                  required
                  value={name}
                  maxLength={100}
                  autoComplete="name"
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
            )}
            <Field label="Adresa e emailit">
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field
              label="Fjalëkalimi"
              hint={register ? "Të paktën 12 karaktere." : undefined}
            >
              <input
                type="password"
                required
                minLength={register ? 12 : 1}
                maxLength={128}
                autoComplete={register ? "new-password" : "current-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <ErrorBox error={error} />
            <button className="full-width" disabled={busy}>
              {busy
                ? "Duke vazhduar…"
                : register
                  ? "Krijo llogarinë"
                  : "Hyr në platformë"}
              <ChevronRight size={18} />
            </button>
          </form>
          <p className="auth-switch">
            {register ? "Keni një llogari?" : "Nuk keni një llogari?"}{" "}
            <button
              className="text-button"
              onClick={() => {
                setRegister(!register);
                setError(undefined);
              }}
            >
              {register ? "Hyni këtu" : "Regjistrohuni"}
            </button>
          </p>
          <div className="privacy">
            <ShieldCheck size={17} />
            Projektet janë private për llogarinë tuaj.
          </div>
        </div>
      </section>
    </div>
  );
}
