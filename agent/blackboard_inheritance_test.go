package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"

	actool "github.com/Autumn-27/norma/tool"
	"github.com/hypnguyen1209/V-ARTEX/db"
)

func callReadJSON(t *testing.T, tool actool.CoreTool, input string) any {
	t.Helper()
	result, err := tool.Call(context.Background(), json.RawMessage(input), nil)
	if err != nil {
		t.Fatalf("tool call: %v", err)
	}
	var out any
	if err := json.Unmarshal([]byte(result.Flatten()), &out); err != nil {
		t.Fatalf("decode tool result: %v; raw=%s", err, result.Flatten())
	}
	return out
}

func TestGraphOverviewKeepsAssociatedCompanyAssetsInTaskContext(t *testing.T) {
	d := testDB(t)
	defer d.Close()

	companies := d.Companies()
	companyID, _, err := companies.UpsertCompany(fmt.Sprintf("overview-scope-%d", time.Now().UnixNano()), "")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = companies.DeleteCompany(companyID) })

	domain := fmt.Sprintf("overview-scope-%d.invalid", companyID)
	ip := fmt.Sprintf("2001:db8:%x::42", companyID%0xffff)
	cidr := fmt.Sprintf("2001:db8:%x:1::/64", companyID%0xffff)
	icp := fmt.Sprintf("Beijing ICP filing %d", companyID)
	keyword := fmt.Sprintf("Scope Company %d", companyID)
	inputs := []db.ScopeInput{
		{Kind: "domain", Value: domain},
		{Kind: "ip", Value: ip},
		{Kind: "cidr", Value: cidr},
		{Kind: "icp", Value: icp},
		{Kind: "keyword", Value: keyword},
	}
	added, skipped, invalid, scopeErrors := companies.AddScopeInputs(companyID, inputs, "task context test")
	if added != len(inputs) || skipped != 0 || invalid != 0 || len(scopeErrors) != 0 {
		t.Fatalf("add company scope: added=%d skipped=%d invalid=%d errors=%v", added, skipped, invalid, scopeErrors)
	}
	assets := d.Assets()
	assetID, err := assets.UpsertRootDomain(db.UpsertRootDomainReq{Domain: domain})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _, _ = assets.DeleteByIDs([]int64{assetID}) })

	task, err := d.CreateTaskWithOptions("company context", "read configured scope", db.TaskCreateOptions{
		CompanyIDs: []int64{companyID},
	})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.DeleteTask(task.ID) })

	tools := NewToolSet(d.Exploration(task.ExplorationID), "planner")
	tools.SetTaskID(task.ID)
	tools.SetAssetStore(assets, companies)
	linkedAssets, err := assets.QueryByTask(task.ID, "root_domain", 10, 0)
	if err != nil || len(linkedAssets) != 1 || linkedAssets[0].ID != assetID {
		t.Fatalf("company asset was not linked to task: assets=%+v err=%v", linkedAssets, err)
	}
	if linkedAssets[0].TaskSource != "company" || !strings.Contains(linkedAssets[0].TaskSourceSummary, companiesName(t, companies, companyID)) {
		t.Fatalf("company asset provenance missing: %+v", linkedAssets[0])
	}
	overview := tools.graphOverviewData()
	coverage, ok := overview["coverage"].(map[string]any)
	if !ok {
		t.Fatalf("coverage missing: %#v", overview["coverage"])
	}
	if _, exists := coverage["scope"]; exists {
		t.Fatalf("graph overview unexpectedly restored removed scope payload: %#v", coverage["scope"])
	}
	if hc, _ := coverage["host_count"].(int); hc < 1 {
		t.Fatalf("company asset host not counted in agent context: %#v", coverage["host_count"])
	}
	untested := callReadJSON(t, tools.listUntestedAssets(), `{"type":"root_domain","page":1,"page_size":10}`)
	if !strings.Contains(fmt.Sprint(untested), domain) {
		t.Fatalf("company asset missing from untested backlog: %#v", untested)
	}
	byTask := callReadJSON(t, tools.listAssets(), fmt.Sprintf(
		`{"dsl":"task_id==%d","type":"root_domain","limit":10}`, task.ID,
	))
	if !strings.Contains(fmt.Sprint(byTask), domain) {
		t.Fatalf("company asset missing from task-scoped agent query: %#v", byTask)
	}
	byCompany := callReadJSON(t, tools.listAssets(), fmt.Sprintf(
		`{"dsl":"company_id==%d","type":"root_domain","limit":10}`, companyID,
	))
	if !strings.Contains(fmt.Sprint(byCompany), domain) {
		t.Fatalf("company asset missing from company-scoped agent query: %#v", byCompany)
	}
	assetJSON, _ := json.Marshal(assetID)
	intentID, err := tools.addOneIntent(intentItem{
		Summary:  "test associated company asset",
		AssetIDs: []json.RawMessage{assetJSON},
	})
	if err != nil {
		t.Fatal(err)
	}
	workerAssets, err := assets.IntentAssets(task.ID)
	if err != nil || len(workerAssets) != 1 || workerAssets[0].IntentID != intentID || workerAssets[0].AssetID != assetID {
		t.Fatalf("worker target did not retain company asset: assets=%+v err=%v", workerAssets, err)
	}

	coverageDisabled := false
	disabledTask, err := d.CreateTaskWithOptions("company context without coverage", "still expose company assets", db.TaskCreateOptions{
		CompanyIDs: []int64{companyID}, CoverageEnabled: &coverageDisabled,
	})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.DeleteTask(disabledTask.ID) })
	disabledTools := NewToolSet(d.Exploration(disabledTask.ExplorationID), "planner")
	disabledTools.SetTaskID(disabledTask.ID)
	disabledTools.SetCoverageEnabled(false)
	disabledTools.SetAssetStore(assets, companies)
	disabledOverview := disabledTools.graphOverviewData()
	disabledCoverage, ok := disabledOverview["coverage"].(map[string]any)
	if !ok {
		t.Fatalf("coverage-disabled task lost asset context: %#v", disabledOverview["coverage"])
	}
	if hc, _ := disabledCoverage["host_count"].(int); hc < 1 {
		t.Fatalf("coverage-disabled task lost company asset host count: %#v", disabledCoverage["host_count"])
	}
	if _, exists := disabledCoverage["denominator"]; exists {
		t.Fatalf("coverage-disabled task unexpectedly exposed metrics: %#v", disabledCoverage)
	}
	if linked, err := assets.QueryByTask(disabledTask.ID, "root_domain", 10, 0); err != nil || len(linked) != 1 || linked[0].ID != assetID {
		t.Fatalf("coverage-disabled task asset link=%+v err=%v", linked, err)
	}
	disabledIntentID, err := disabledTools.addOneIntent(intentItem{
		Summary:  "test associated company asset without coverage metrics",
		AssetIDs: []json.RawMessage{assetJSON},
	})
	if err != nil {
		t.Fatal(err)
	}
	disabledWorkerAssets, err := assets.IntentAssets(disabledTask.ID)
	if err != nil || len(disabledWorkerAssets) != 1 || disabledWorkerAssets[0].IntentID != disabledIntentID || disabledWorkerAssets[0].AssetID != assetID {
		t.Fatalf("coverage-disabled worker target=%+v err=%v", disabledWorkerAssets, err)
	}
}

func companiesName(t *testing.T, companies *db.CompanyStore, companyID int64) string {
	t.Helper()
	company, err := companies.GetCompany(companyID)
	if err != nil || company == nil {
		t.Fatalf("company %d: company=%+v err=%v", companyID, company, err)
	}
	return company.Name
}

func TestGetWorkerTraceStepIDsDegradeGracefully(t *testing.T) {
	d := testDB(t)
	defer d.Close()

	task, err := d.CreateTask("trace-cap", "goal", nil, 0, 0)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.DeleteTask(task.ID) })
	store := d.Exploration(task.ExplorationID)
	intent, err := store.AddIntent(map[string]any{"summary": "cap work"}, 1, nil, "planner")
	if err != nil {
		t.Fatal(err)
	}

	var stepIDs []int64
	for i := range 6 {
		sid, err := store.AppendActivity(db.Activity{
			NodeID: &intent, Worker: "w", Kind: "result", Tool: "HTTP",
			Summary: fmt.Sprintf("step %d", i), Detail: fmt.Sprintf("detail %d", i),
		})
		if err != nil {
			t.Fatal(err)
		}
		stepIDs = append(stepIDs, sid)
	}

	tools := NewToolSet(store, "worker")
	tools.SetAssetStore(d.Assets(), d.Companies())

	// Request 7 ids: a duplicate of the first, an invalid 0, then all 6 real ids.
	// After dedup/cleanup that is 6 valid ids — one over the cap.
	requested := []int64{stepIDs[0], stepIDs[0], 0, stepIDs[1], stepIDs[2], stepIDs[3], stepIDs[4], stepIDs[5]}
	input, _ := json.Marshal(map[string]any{"intent_id": intent, "step_ids": requested})
	res := callReadJSON(t, tools.getWorkerTrace(), string(input)).(map[string]any)

	returned, _ := res["returned_step_ids"].([]any)
	if len(returned) != 5 {
		t.Fatalf("returned_step_ids=%v, want the first 5", res["returned_step_ids"])
	}
	// First 5 distinct valid ids, in request order.
	wantReturned := []int64{stepIDs[0], stepIDs[1], stepIDs[2], stepIDs[3], stepIDs[4]}
	for i, raw := range returned {
		if int64(raw.(float64)) != wantReturned[i] {
			t.Fatalf("returned[%d]=%v, want %d", i, raw, wantReturned[i])
		}
	}
	omitted, _ := res["omitted_step_ids"].([]any)
	if len(omitted) != 1 || int64(omitted[0].(float64)) != stepIDs[5] {
		t.Fatalf("omitted_step_ids=%v, want [%d]", res["omitted_step_ids"], stepIDs[5])
	}
	if notice, _ := res["notice"].(string); notice == "" {
		t.Fatalf("notice missing — model would not know a step was deferred")
	}
	if steps, _ := res["steps"].([]any); len(steps) != 5 {
		t.Fatalf("steps=%d, want 5 detail rows", len(steps))
	}

	// At or under the cap: no notice, no omitted list.
	okInput, _ := json.Marshal(map[string]any{"intent_id": intent, "step_ids": stepIDs[:3]})
	okRes := callReadJSON(t, tools.getWorkerTrace(), string(okInput)).(map[string]any)
	if _, hasNotice := okRes["notice"]; hasNotice {
		t.Fatalf("notice present for an in-cap request: %#v", okRes["notice"])
	}
	if _, hasOmitted := okRes["omitted_step_ids"]; hasOmitted {
		t.Fatalf("omitted_step_ids present for an in-cap request: %#v", okRes["omitted_step_ids"])
	}
}
