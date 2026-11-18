package db

import (
	"fmt"
	"testing"
)

func TestExplorationFlow(t *testing.T) {
	d, err := Open(testDSN(t))
	if err != nil {
		t.Skipf("postgres unavailable (%v) — skipping", err)
	}
	defer d.Close()

	expID, err := d.CreateExploration("test", "Compromise the test target")
	if err != nil {
		t.Fatal(err)
	}
	defer d.Exec(`DELETE FROM explorations WHERE id=$1`, expID) // cascades nodes/edges/activity
	es := d.Exploration(expID)

	// goal node + two intents
	goal, err := es.AddGoal(map[string]any{"text": "getadmin", "vulnclass": "authz"}, "human")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := es.AddIntent(map[string]any{"summary": "enumerate endpoints"}, 5, nil, "planner"); err != nil {
		t.Fatal(err)
	}
	i2, err := es.AddIntent(map[string]any{"summary": "test idor"}, 8, nil, "planner")
	if err != nil {
		t.Fatal(err)
	}

	// frontier ordered by priority desc → i2(8) before i1(5)
	fr, err := es.Frontier(10)
	if err != nil {
		t.Fatal(err)
	}
	if len(fr) != 2 || fr[0].ID != i2 {
		t.Fatalf("frontier order wrong: %+v", fr)
	}

	// atomic claim: first wins, second on same id fails
	ok, err := es.ClaimIntent(i2, "worker-1")
	if err != nil || !ok {
		t.Fatalf("claim i2: ok=%v err=%v", ok, err)
	}
	ok2, _ := es.ClaimIntent(i2, "worker-2")
	if ok2 {
		t.Fatalf("double-claim should fail")
	}

	// fact yields from intent, proves goal
	fact, err := es.AddNode("fact", map[string]any{"summary": "found admin login"}, 9, "confirmed", "worker-1", nil)
	if err != nil {
		t.Fatal(err)
	}
	if err := es.Link(i2, "yields", fact); err != nil {
		t.Fatal(err)
	}
	if err := es.Link(fact, "proves", goal); err != nil {
		t.Fatal(err)
	}
	if err := es.SetNodeState(goal, "met"); err != nil {
		t.Fatal(err)
	}

	// activity poll by id cursor
	id1, err := es.AppendActivity(Activity{Worker: "worker-1", Kind: "tool_use", Tool: "Bash", Summary: "ran curl", Detail: "full output"})
	if err != nil {
		t.Fatal(err)
	}
	items, cursor, err := es.ActivityList(nil, 0, 100)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 || cursor != id1 {
		t.Fatalf("activity list: items=%d cursor=%d", len(items), cursor)
	}
	det, _ := es.ActivityDetail(id1)
	if det != "full output" {
		t.Fatalf("detail want 'full output', got %q", det)
	}
	// incremental: nothing new after cursor
	items2, _, _ := es.ActivityList(nil, cursor, 100)
	if len(items2) != 0 {
		t.Fatalf("incremental poll should be empty, got %d", len(items2))
	}

	// stats
	st, _ := es.Stats()
	if st["intent"] != 2 || st["goal"] != 1 || st["finding"] != 1 {
		t.Fatalf("stats: %+v", st)
	}
}

func TestNodesPageQueryMatchesID(t *testing.T) {
	d, err := Open(testDSN(t))
	if err != nil {
		t.Skipf("postgres unavailable (%v) — skipping", err)
	}
	defer d.Close()

	expID, err := d.CreateExploration("test", "ID search")
	if err != nil {
		t.Fatal(err)
	}
	defer d.Exec(`DELETE FROM explorations WHERE id=$1`, expID)
	es := d.Exploration(expID)

	target, err := es.AddNode("fact", map[string]any{"summary": "needle-alpha"}, 0, "confirmed", "worker-a", nil)
	if err != nil {
		t.Fatal(err)
	}
	other, err := es.AddNode("fact", map[string]any{"summary": "unrelated-beta"}, 0, "confirmed", "worker-b", nil)
	if err != nil {
		t.Fatal(err)
	}

	onlyTarget := func(label, q string) {
		t.Helper()
		nodes, total, err := es.NodesPage(NodeFilter{Query: q}, 1, 50)
		if err != nil {
			t.Fatalf("%s: %v", label, err)
		}
		if total != 1 || len(nodes) != 1 || nodes[0].ID != target {
			t.Fatalf("%s: q=%q total=%d nodes=%+v, want single node %d", label, q, total, nodes, target)
		}
	}

	onlyTarget("bare id", fmt.Sprint(target))
	onlyTarget("hash id", "#"+fmt.Sprint(target))
	onlyTarget("payload still works", "needle-alpha")

	// A non-matching numeric id returns nothing (and does not accidentally match other).
	if nodes, total, err := es.NodesPage(NodeFilter{Query: fmt.Sprint(target + other + 1000)}, 1, 50); err != nil {
		t.Fatal(err)
	} else if total != 0 || len(nodes) != 0 {
		t.Fatalf("non-existent id: total=%d nodes=%+v, want empty", total, nodes)
	}
}
