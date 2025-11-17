const fs = require('fs');
const path = require('path');
try {
  const postcss = require('postcss');
  const tailwindPostcss = require('@tailwindcss/postcss');
  const autoprefixer = require('autoprefixer');

  const resolvedTailwindPkg = require.resolve('tailwindcss/package.json');
  const tailwindPkg = require(resolvedTailwindPkg);
  console.log('resolved tailwindcss package.json at:', resolvedTailwindPkg);
  console.log('tailwind version:', tailwindPkg.version);

  const css = fs.readFileSync(path.join(__dirname, '..', 'src', 'index.css'), 'utf8');
  postcss([tailwindPostcss(), autoprefixer()])
    .process(css, { from: path.join(__dirname, '..', 'src', 'index.css') })
    .then(result => {
      console.log('PostCSS processing succeeded. Output length:', result.css.length);
    })
    .catch(err => {
      console.error('PostCSS processing failed:');
      console.error(err.stack || err.toString());
      if (err.name) console.error('Error name:', err.name);
      process.exit(1);
    });
  // Try a minimal reproduction
  const simple = "@tailwind base; @tailwind components; @tailwind utilities; .x { @apply bg-white; }";
  postcss([tailwindPostcss(), autoprefixer()])
    .process(simple, { from: undefined })
    .then(result => {
      console.log('Minimal PostCSS processing succeeded. Output length:', result.css.length);
    })
    .catch(err => {
      console.error('Minimal PostCSS processing failed:');
      console.error(err.stack || err.toString());
    });
} catch (e) {
  console.error('Diagnostic script failed to run:');
  console.error(e.stack || e.toString());
  process.exit(2);
}
