from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WEB_ROOT = ROOT / "apps/web"


def test_representative_codegen_files_compile_with_react_tailwind_and_antd(tmp_path: Path) -> None:
    (tmp_path / "Generated.tsx").write_text(
        """
import { Button } from "antd";
import "./Generated.css";

export default function Generated() {
  return (
    <main className="flex flex-col gap-4 generated-root">
      <img src="/assets/logo.png" alt="Logo" />
      <Button type="primary">Continue</Button>
    </main>
  );
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "Generated.css").write_text(".generated-root { padding: 24px; }\n", encoding="utf-8")
    (tmp_path / "global.d.ts").write_text(
        'declare module "*.css";\n',
        encoding="utf-8",
    )
    (tmp_path / "tsconfig.json").write_text(
        json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2022",
                    "module": "ESNext",
                    "moduleResolution": "Bundler",
                    "jsx": "react-jsx",
                    "strict": True,
                    "noEmit": True,
                    "skipLibCheck": True,
                    "baseUrl": str(tmp_path),
                    "paths": {
                        "react": [str(WEB_ROOT / "node_modules/react")],
                        "react/*": [str(WEB_ROOT / "node_modules/react/*")],
                        "react/jsx-runtime": [str(WEB_ROOT / "node_modules/@types/react/jsx-runtime.d.ts")],
                        "antd": [str(WEB_ROOT / "node_modules/antd")],
                    },
                },
                "include": ["Generated.tsx", "global.d.ts"],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(WEB_ROOT / "node_modules/.bin/tsc"), "--project", str(tmp_path / "tsconfig.json")],
        cwd=WEB_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
