package server

import (
	"context"
	"iter"

	"github.com/Autumn-27/norma/llm"
)

// retestProvider is a minimal llm.Provider used by engine settlement tests.
// It replaces the provider helper that lived in the removed retest tests.
type retestProvider struct {
	complete func(context.Context, llm.CompletionRequest) (llm.Message, string, llm.Usage, error)
}

func (p retestProvider) Complete(ctx context.Context, req llm.CompletionRequest) (llm.Message, string, llm.Usage, error) {
	return p.complete(ctx, req)
}

func (p retestProvider) Stream(context.Context, llm.CompletionRequest) iter.Seq2[llm.StreamEvent, error] {
	return func(func(llm.StreamEvent, error) bool) {}
}
