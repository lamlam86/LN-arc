package db

// MigrateReconOnly removes database rows that belonged to the retired
// exploitation/finding workflow: the reporter and retester agents, their
// finding triggers, and the finding-only tool catalog rows.
//
// It is one-shot and idempotent, guarded by a settings flag. Historical
// findings tables are left in place so existing installations do not lose
// data unexpectedly; new installations never create them (see schema.sql).
func (d *DB) MigrateReconOnly() error {
	if v, _, _ := d.GetSetting("recon_only_migration_v1"); v == "done" {
		return nil
	}
	stmts := []string{
		`DELETE FROM agent_triggers WHERE agent_key IN ('reporter','retester')`,
		// Older installations still carry the retired finding trigger column.
		// Fresh installations never create it (see schema.sql), so guard both
		// the cleanup delete and the drop behind an existence check.
		`DO $$
		BEGIN
			IF EXISTS (
				SELECT 1 FROM information_schema.columns
				WHERE table_schema = current_schema()
					AND table_name = 'agent_triggers'
					AND column_name = 'on_finding'
			) THEN
				DELETE FROM agent_triggers WHERE on_finding = true;
				ALTER TABLE agent_triggers DROP COLUMN on_finding;
			END IF;
		END $$`,
		`DELETE FROM agents WHERE key IN ('reporter','retester') AND builtin = false`,
		`DELETE FROM tools WHERE key IN ('report_finding','list_findings','list_task_findings','update_finding_report','bind_finding_traffic','get_finding_traffic')`,
	}
	for _, q := range stmts {
		if _, err := d.Exec(q); err != nil {
			return err
		}
	}
	return d.SetSetting("recon_only_migration_v1", "done")
}
