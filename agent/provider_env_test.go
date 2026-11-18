package agent

import "testing"

func TestFromEnvReadsSessionHeader(t *testing.T) {
	t.Setenv("ARTEX_LLM_PROVIDER", "openai")
	t.Setenv("OPENAI_API_KEY", "test-key")
	t.Setenv("ARTEX_LLM_BASE_URL", "https://opencode.ai/inference/go/openai/v1")
	t.Setenv("ARTEX_LLM_MODEL", "deepseek-v4.1-flash")
	t.Setenv("ARTEX_LLM_SESSION_HEADER", " x-opencode-session ")

	cfg, ok := FromEnv()
	if !ok {
		t.Fatal("FromEnv returned ok=false with a key set")
	}
	if cfg.SessionHeaderKey != "x-opencode-session" {
		t.Fatalf("SessionHeaderKey = %q, want x-opencode-session", cfg.SessionHeaderKey)
	}
	if cfg.BaseURL != "https://opencode.ai/inference/go/openai/v1" {
		t.Fatalf("BaseURL = %q", cfg.BaseURL)
	}
	if cfg.Model != "deepseek-v4.1-flash" {
		t.Fatalf("Model = %q", cfg.Model)
	}
}

func TestFromEnvSessionHeaderOptional(t *testing.T) {
	t.Setenv("ARTEX_LLM_PROVIDER", "openai")
	t.Setenv("OPENAI_API_KEY", "test-key")
	t.Setenv("ARTEX_LLM_SESSION_HEADER", "")

	cfg, ok := FromEnv()
	if !ok {
		t.Fatal("FromEnv returned ok=false with a key set")
	}
	if cfg.SessionHeaderKey != "" {
		t.Fatalf("SessionHeaderKey = %q, want empty", cfg.SessionHeaderKey)
	}
}
