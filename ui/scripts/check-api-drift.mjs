// Fails the build when the generated API types differ from the committed copy.
// Outside a git checkout (e.g. a Docker build context) there is nothing to
// compare against, so the check is skipped; CI runs it inside the checkout.
import { spawnSync } from 'node:child_process';

const SCHEMA = 'src/api/schema.d.ts';

const inRepo = spawnSync('git', ['rev-parse', '--is-inside-work-tree'], { encoding: 'utf8' });
if (inRepo.status !== 0) {
  console.log(`check:api skipped: not a git checkout`);
  process.exit(0);
}

const diff = spawnSync('git', ['diff', '--exit-code', '--', SCHEMA], { stdio: 'inherit' });
if (diff.status !== 0) {
  console.error(
    `\n${SCHEMA} drifted from the committed version. ` +
      'Run `python -m app.export_openapi` in backend/ and `npm run gen:api` in ui/, then commit both.',
  );
  process.exit(1);
}
