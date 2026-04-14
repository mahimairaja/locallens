import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { KeyRound, CheckCircle, AlertCircle, Shield } from "lucide-react";

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);
  const [authStatus, setAuthStatus] = useState<{
    auth_enabled: boolean;
    authenticated: boolean;
  } | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("locallens_api_key") || "";
    setApiKey(stored);
    api.getAuthStatus().then(setAuthStatus).catch(() => {});
  }, []);

  const handleSave = () => {
    const trimmed = apiKey.trim();
    if (trimmed) {
      localStorage.setItem("locallens_api_key", trimmed);
    } else {
      localStorage.removeItem("locallens_api_key");
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    // Re-check auth status
    api.getAuthStatus().then(setAuthStatus).catch(() => {});
  };

  const handleClear = () => {
    setApiKey("");
    localStorage.removeItem("locallens_api_key");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    api.getAuthStatus().then(setAuthStatus).catch(() => {});
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h2
        className="text-2xl"
        style={{
          fontFamily: "var(--font-sans)",
          fontWeight: 600,
          color: "var(--text-primary)",
          letterSpacing: "-0.015em",
        }}
      >
        Settings
      </h2>

      {/* Auth Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Shield className="h-4 w-4" style={{ color: "var(--accent)" }} />
            Authentication Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {authStatus ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm" style={{ fontFamily: "var(--font-sans)" }}>
                <span style={{ color: "var(--text-secondary)" }}>Server auth:</span>
                {authStatus.auth_enabled ? (
                  <span className="flex items-center gap-1" style={{ color: "var(--accent)" }}>
                    <KeyRound className="h-3.5 w-3.5" />
                    Enabled
                  </span>
                ) : (
                  <span style={{ color: "var(--text-tertiary)" }}>Disabled (open access)</span>
                )}
              </div>
              {authStatus.auth_enabled && (
                <div className="flex items-center gap-2 text-sm" style={{ fontFamily: "var(--font-sans)" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Your status:</span>
                  {authStatus.authenticated ? (
                    <span className="flex items-center gap-1 text-green-600">
                      <CheckCircle className="h-3.5 w-3.5" />
                      Authenticated
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-500">
                      <AlertCircle className="h-3.5 w-3.5" />
                      Not authenticated
                    </span>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p
              className="text-sm"
              style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-sans)" }}
            >
              Checking...
            </p>
          )}
        </CardContent>
      </Card>

      {/* API Key */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound className="h-4 w-4" style={{ color: "var(--accent)" }} />
            API Key
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p
            className="text-sm"
            style={{ color: "var(--text-secondary)", fontFamily: "var(--font-sans)" }}
          >
            If the server has <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.85em" }}>LOCALLENS_API_KEY</code> set,
            enter the key here to authenticate your requests. The key is stored in your browser's localStorage.
          </p>
          <div className="flex gap-2">
            <Input
              type="password"
              placeholder="Enter API key..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave();
              }}
              className="flex-1"
            />
            <Button onClick={handleSave}>Save</Button>
            {apiKey && (
              <Button variant="outline" onClick={handleClear}>
                Clear
              </Button>
            )}
          </div>
          {saved && (
            <p className="flex items-center gap-1 text-sm text-green-600" style={{ fontFamily: "var(--font-sans)" }}>
              <CheckCircle className="h-3.5 w-3.5" />
              Saved
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
