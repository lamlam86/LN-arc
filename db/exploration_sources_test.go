package db

import (
	"fmt"
	"testing"
)

func TestInheritedActivityReadsRequireTerminalIntent(t *testing.T) {
	d, err := Open(testDSN(t))
	if err != nil {
		t.Skipf("postgres unavailable (%v) - skipping", err)
	}
	defer d.Close()

	expID, err := d.CreateExploration("source activity boundary", "source activity boundary")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _, _ = d.Exec(`DELETE FROM explorations WHERE id=$1`, expID) })
	store := d.Exploration(expID)
	intentID, err := store.AddIntent(map[string]any{"summary": "source work"}, 1, nil, "planner")
	if err != nil {
		t.Fatal(err)
	}
	appendStep := func(kind, summary string) int64 {
		t.Helper()
		id, appendErr := store.AppendActivity(Activity{
			NodeID: &intentID, Worker: "worker", Kind: kind, Summary: summary, Detail: summary + " detail",
		})
		if appendErr != nil {
			t.Fatal(appendErr)
		}
		return id
	}
	textID := appendStep("text", "shared text")
	thinkingID := appendStep("thinking", "private reasoning")
	usageID := appendStep("usage", "private accounting")
	resultID := appendStep("result", "shared result")
	if err := store.SetIntentState(intentID, "done"); err != nil {
		t.Fatal(err)
	}

	page, more, err := store.ActivityPageForTerminalIntent(intentID, 0, 10)
	if err != nil || more || len(page) != 2 || page[0].ID != textID || page[1].ID != resultID {
		t.Fatalf("terminal page boundary: page=%+v more=%v err=%v", page, more, err)
	}
	list, cursor, err := store.ActivityListForTerminalIntent(intentID, 0, 10)
	if err != nil || len(list) != 2 || cursor != resultID {
		t.Fatalf("terminal list boundary: list=%+v cursor=%d err=%v", list, cursor, err)
	}
	trace, err := store.ActivityTraceForTerminalIntent(intentID, 10)
	if err != nil || len(trace) != 2 {
		t.Fatalf("terminal trace boundary: trace=%+v err=%v", trace, err)
	}
	hits, err := store.ActivityTraceSearchForTerminalIntent(intentID, "shared", 10)
	if err != nil || len(hits) != 2 {
		t.Fatalf("terminal search boundary: hits=%+v err=%v", hits, err)
	}
	details, err := store.ActivityByIDsForTerminalIntents([]int64{textID, thinkingID, usageID, resultID})
	if err != nil || len(details) != 2 || details[0].ID != textID || details[1].ID != resultID {
		t.Fatalf("terminal detail boundary: details=%+v err=%v", details, err)
	}

	// Reopening a source intent must close every inherited activity read even if
	// callers still hold a stale terminal-state snapshot.
	if err := store.SetIntentState(intentID, "running"); err != nil {
		t.Fatal(err)
	}
	page, _, err = store.ActivityPageForTerminalIntent(intentID, 0, 10)
	if err != nil || len(page) != 0 {
		t.Fatalf("reopened intent leaked through page: page=%+v err=%v", page, err)
	}
	list, _, err = store.ActivityListForTerminalIntent(intentID, 0, 10)
	if err != nil || len(list) != 0 {
		t.Fatalf("reopened intent leaked through list: list=%+v err=%v", list, err)
	}
	trace, err = store.ActivityTraceForTerminalIntent(intentID, 10)
	if err != nil || len(trace) != 0 {
		t.Fatalf("reopened intent leaked through trace: trace=%+v err=%v", trace, err)
	}
	hits, err = store.ActivityTraceSearchForTerminalIntent(intentID, "shared", 10)
	if err != nil || len(hits) != 0 {
		t.Fatalf("reopened intent leaked through search: hits=%+v err=%v", hits, err)
	}
	details, err = store.ActivityByIDsForTerminalIntents([]int64{textID, resultID})
	if err != nil || len(details) != 0 {
		t.Fatalf("reopened intent leaked through detail: details=%+v err=%v", details, err)
	}
}

func TestTaskAssetContextUsesDirectSourceScopeAndAnchors(t *testing.T) {
	d, err := Open(testDSN(t))
	if err != nil {
		t.Skipf("postgres unavailable (%v) - skipping", err)
	}
	defer d.Close()

	grand, err := d.CreateTask("grand assets", "grand goal", nil, 0, 0)
	if err != nil {
		t.Fatal(err)
	}
	source, err := d.CreateTaskWithOptions("source assets", "source goal", TaskCreateOptions{SourceTaskIDs: []int64{grand.ID}})
	if err != nil {
		t.Fatal(err)
	}
	current, err := d.CreateTaskWithOptions("current assets", "current goal", TaskCreateOptions{SourceTaskIDs: []int64{source.ID}})
	if err != nil {
		t.Fatal(err)
	}
	assets := d.Assets()
	sourceTestedDomain := fmt.Sprintf("context-tested-%d.invalid", source.ID)
	sourceUntestedDomain := fmt.Sprintf("context-untested-%d.invalid", source.ID)
	sourceAnchoredOnlyDomain := fmt.Sprintf("context-anchor-only-%d.invalid", source.ID)
	grandDomain := fmt.Sprintf("context-grand-%d.invalid", grand.ID)
	sourceTestedID, err := assets.UpsertRootDomain(UpsertRootDomainReq{Domain: sourceTestedDomain, TaskID: source.ID})
	if err != nil {
		t.Fatal(err)
	}
	sourceUntestedID, err := assets.UpsertRootDomain(UpsertRootDomainReq{Domain: sourceUntestedDomain, TaskID: source.ID})
	if err != nil {
		t.Fatal(err)
	}
	sourceAnchoredOnlyID, err := assets.UpsertRootDomain(UpsertRootDomainReq{Domain: sourceAnchoredOnlyDomain, TaskID: source.ID})
	if err != nil {
		t.Fatal(err)
	}
	grandID, err := assets.UpsertRootDomain(UpsertRootDomainReq{Domain: grandDomain, TaskID: grand.ID})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		_ = d.DeleteTask(current.ID)
		_ = d.DeleteTask(source.ID)
		_ = d.DeleteTask(grand.ID)
		_, _ = assets.DeleteByIDs([]int64{sourceTestedID, sourceUntestedID, sourceAnchoredOnlyID, grandID})
	})
	if _, err := assets.AddAgentScope(source.ID, "root_domain", sourceTestedDomain, "test", "agent"); err != nil {
		t.Fatal(err)
	}
	if _, err := assets.AddAgentScope(source.ID, "root_domain", sourceUntestedDomain, "test", "agent"); err != nil {
		t.Fatal(err)
	}
	if _, err := assets.AddAgentScope(grand.ID, "root_domain", grandDomain, "test", "agent"); err != nil {
		t.Fatal(err)
	}
	if _, err := d.Exploration(source.ExplorationID).AddNode(KindFact, map[string]any{"summary": "tested source asset"}, 0, "confirmed", "worker", []int64{sourceTestedID}); err != nil {
		t.Fatal(err)
	}
	if _, err := d.Exploration(source.ExplorationID).AddNode(KindFact, map[string]any{"summary": "anchored-only source asset"}, 0, "confirmed", "worker", []int64{sourceAnchoredOnlyID}); err != nil {
		t.Fatal(err)
	}
	if _, err := d.Exploration(grand.ExplorationID).AddNode(KindFact, map[string]any{"summary": "indirect tested asset"}, 0, "confirmed", "worker", []int64{grandID}); err != nil {
		t.Fatal(err)
	}

	scopes, err := assets.ListTaskScopeWithSources(current.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(scopes) != 2 || scopes[0].TaskID != source.ID || scopes[1].TaskID != source.ID {
		t.Fatalf("direct source scopes only: %+v", scopes)
	}
	cov, err := assets.TaskCoverageWithSources(current.ID)
	if err != nil {
		t.Fatal(err)
	}
	if cov.Denominator != 3 || cov.Tested != 2 {
		t.Fatalf("combined coverage: %+v", cov)
	}
	untested, total, err := assets.ListUntestedAssetsWithSources(current.ID, "", 10, 0)
	if err != nil {
		t.Fatal(err)
	}
	if total != 1 || len(untested) != 1 || untested[0].ID != sourceUntestedID {
		t.Fatalf("combined untested assets: total=%d assets=%+v", total, untested)
	}
	hosts, err := assets.HostsByTaskWithSources(current.ID)
	if err != nil {
		t.Fatal(err)
	}
	hostSet := map[string]bool{}
	for _, host := range hosts {
		hostSet[host] = true
	}
	if !hostSet[sourceTestedDomain] || !hostSet[sourceUntestedDomain] || !hostSet[sourceAnchoredOnlyDomain] || hostSet[grandDomain] {
		t.Fatalf("direct source hosts only: %v", hosts)
	}
	refs, err := d.Exploration(current.ExplorationID).AssetRefsWithSources(sourceAnchoredOnlyID)
	if err != nil || len(refs) != 1 || !refs[0].Inherited || refs[0].SourceTaskID != source.ID || refs[0].Kind != KindFact {
		t.Fatalf("source asset refs provenance: refs=%+v err=%v", refs, err)
	}
	grandRefs, err := d.Exploration(current.ExplorationID).AssetRefsWithSources(grandID)
	if err != nil || len(grandRefs) != 0 {
		t.Fatalf("indirect source asset refs leaked: refs=%+v err=%v", grandRefs, err)
	}
	graph, err := assets.BuildCoverageGraph(current.ID, current.ExplorationID)
	if err != nil {
		t.Fatal(err)
	}
	seenAnchoredOnly := false
	for _, node := range graph.Nodes {
		if node.AssetID == sourceAnchoredOnlyID {
			seenAnchoredOnly = node.Tested && node.InScope
		}
	}
	if !seenAnchoredOnly {
		t.Fatalf("anchored-only source asset missing from coverage graph: %+v", graph.Nodes)
	}
}
