import {
  useState,
  useId,
  cloneElement,
  isValidElement,
  type ReactNode,
  type ReactElement,
} from "react";
import { X, AlertCircle, LoaderCircle, Inbox } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="overlay">
          <Dialog.Content
            aria-describedby={undefined}
            className={`modal ${wide ? "wide" : ""}`}
          >
            <header>
              <Dialog.Title asChild>
                <h2>{title}</h2>
              </Dialog.Title>
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Mbyll"
                >
                  <X size={20} />
                </button>
              </Dialog.Close>
            </header>
            {children}
          </Dialog.Content>
        </Dialog.Overlay>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {isValidElement(children)
        ? cloneElement(children as ReactElement<any>, {
            id,
            "aria-describedby": hint ? id + "-hint" : undefined,
          })
        : children}
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </div>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <div className="error" role="alert">
      <AlertCircle size={18} />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  ) : null;
}
export function Empty({
  text = "Nuk ka të dhëna ende.",
  action,
}: {
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <Inbox size={34} />
      <p>{text}</p>
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={22} /> Duke ngarkuar…
    </div>
  );
}
export function Badge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    approved: "Miratuar",
    rejected: "Refuzuar",
    pending: "Në pritje",
    finalized: "Finalizuar",
    draft: "Draft",
    high: "Besim i lartë",
    medium: "Për rishikim",
    low: "Besim i ulët",
    no_match: "Pa përputhje",
    active: "Aktiv",
    inactive: "Arkivuar",
  };
  return <span className={`badge ${status}`}>{labels[status] || status}</span>;
}
export function Confirm({
  title,
  detail,
  onConfirm,
  onClose,
}: {
  title: string;
  detail: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <Modal
      title={title}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <p className="confirm-detail">{detail}</p>
      <ErrorBox error={error} />
      <footer>
        <button disabled={busy} className="secondary" onClick={onClose}>
          Anulo
        </button>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onConfirm();
              onClose();
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Duke ruajtur…" : "Po, konfirmoj"}
        </button>
      </footer>
    </Modal>
  );
}
