"""
Fault Injector - Inject faults into the dbt pipeline environment
Supports: file modification, database modification, config changes
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


class FaultInjector:
    def __init__(self, env_root: Path):
        self.env_root = env_root
        self.dbt_project = env_root / "dbt" / "dbt_demo"
        self.backup_dir = env_root / "fault_injection" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.faults_file = env_root / "fault_injection" / "fault_definitions.json"

        with open(self.faults_file, 'r', encoding='utf-8') as f:
            self.faults_data = json.load(f)
        self.faults = {f["fault_id"]: f for f in self.faults_data["faults"]}

    def inject(self, fault_id: str) -> dict:
        """Inject specified fault"""
        if fault_id not in self.faults:
            return {"success": False, "error": f"Fault {fault_id} not found"}

        fault = self.faults[fault_id]
        injection_type = fault.get("injection_type", "")

        handlers = {
            "file_modify": self._inject_file_modify,
            "database_modify": self._inject_database_modify,
            "config_modify": self._inject_config_modify,
            "resource_limit": self._inject_resource_limit,
            "infrastructure": self._inject_infrastructure,
            "concurrency_test": self._inject_concurrency,
        }

        handler = handlers.get(injection_type)
        if not handler:
            return {"success": False, "error": f"Unknown injection type: {injection_type}"}

        try:
            result = handler(fault)
            result["fault_id"] = fault_id
            result["fault"] = fault
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reset(self, fault_id: str = None) -> dict:
        """Reset environment"""
        try:
            if fault_id:
                backup_path = self.backup_dir / fault_id
                if backup_path.exists():
                    self._restore_backup(backup_path)
            else:
                for backup in self.backup_dir.iterdir():
                    if backup.is_dir():
                        self._restore_backup(backup)

            return {"success": True, "message": "Environment reset"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backup_file(self, fault_id: str, file_path: Path):
        """Backup file before modification"""
        backup_dir = self.backup_dir / fault_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        rel_path = file_path.relative_to(self.env_root)
        backup_file = backup_dir / rel_path
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_file)

    def _restore_backup(self, backup_dir: Path):
        """Restore from backup"""
        for root, dirs, files in os.walk(backup_dir):
            for f in files:
                src = Path(root) / f
                rel = src.relative_to(backup_dir)
                dst = self.env_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    def _inject_file_modify(self, fault: dict) -> dict:
        """Inject fault via file modification"""
        target_file = fault.get("target_file", "")
        injection = fault.get("injection", "")

        file_path = self.dbt_project / target_file
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {target_file}"}

        self._backup_file(fault["fault_id"], file_path)

        original = file_path.read_text(encoding='utf-8')
        modified = self._apply_file_injection(original, fault)
        file_path.write_text(modified, encoding='utf-8')

        return {
            "success": True,
            "file": str(target_file),
            "injection": injection,
        }

    def _apply_file_injection(self, content: str, fault: dict) -> str:
        """Apply specific file modification based on fault type"""
        fault_id = fault["fault_id"]

        if fault_id == "DEF-01":
            content = content.replace("materialized: table", "materialized: tabel", 1)
        elif fault_id == "DEF-02":
            content = content.replace("from source",
                "from source\n    where order_date >= '{{ var(''start_date'') }}'")
        elif fault_id == "DEF-04":
            content = content.replace("first_name,\n        last_name",
                "first_name\n        last_name")
        elif fault_id == "DEF-05":
            content = content.replace("ref('stg_orders')", "ref('stg_order_history')")
        elif fault_id == "DEF-07":
            content = content.replace("select", "selct", 1)

        return content

    def _inject_database_modify(self, fault: dict) -> dict:
        """Inject fault via database modification"""
        return {
            "success": True,
            "note": "Database modification requires running PostgreSQL container",
            "sql": self._generate_fault_sql(fault),
        }

    def _generate_fault_sql(self, fault: dict) -> str:
        """Generate SQL for database fault injection"""
        fault_id = fault["fault_id"]
        sql_map = {
            "DAT-01": "ALTER TABLE raw.customers DROP COLUMN email;",
            "DAT-02": "ALTER TABLE raw.orders ALTER COLUMN customer_id TYPE VARCHAR(20);",
            "DAT-03": "INSERT INTO raw.orders VALUES (1, 1, '2024-01-01', 'test', 0);",
            "DAT-04": "INSERT INTO raw.orders VALUES (9999, 9999, '2024-01-01', 'test', 0);",
            "DAT-05": "INSERT INTO raw.customers (customer_id, first_name) VALUES (9999, 'Test');",
            "EXE-01": "REVOKE CREATE ON SCHEMA staging FROM dbt_user;",
        }
        return sql_map.get(fault_id, "-- SQL not defined")

    def _inject_config_modify(self, fault: dict) -> dict:
        return {"success": True, "note": "Config modification"}

    def _inject_resource_limit(self, fault: dict) -> dict:
        return {"success": True, "note": "Resource limit simulation"}

    def _inject_infrastructure(self, fault: dict) -> dict:
        return {"success": True, "note": "Infrastructure change"}

    def _inject_concurrency(self, fault: dict) -> dict:
        return {"success": True, "note": "Concurrency test setup"}


def main():
    import sys
    env_root = Path(__file__).parent.parent

    injector = FaultInjector(env_root)

    if len(sys.argv) < 2:
        print("Usage: python inject_fault.py <fault_id> [--reset]")
        print("Available faults:")
        for fid in sorted(injector.faults.keys()):
            f = injector.faults[fid]
            print(f"  {fid}: {f['title']}")
        return

    fault_id = sys.argv[1]

    if "--reset" in sys.argv:
        result = injector.reset(fault_id)
    else:
        result = injector.inject(fault_id)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
