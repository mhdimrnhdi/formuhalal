import tailwindcss from '@tailwindcss/postcss';
import autoprefixer from 'autoprefixer';
import fs from 'fs';
import postcss from 'postcss';
import chokidar from 'chokidar';

async function build() {
  const input = fs.readFileSync('./styles/input.css', 'utf8');
  const result = await postcss([
    tailwindcss(),
    autoprefixer
  ]).process(input, {
    from: './styles/input.css',
    to: './dist/styles.css'
  });
  fs.mkdirSync('./dist', { recursive: true });
  fs.writeFileSync('./dist/styles.css', result.css);
  console.log(`Built: ${(result.css.length / 1024).toFixed(1)}KB`);
}

if (process.argv.includes('--watch')) {
  build().catch(console.error);
  chokidar.watch(['./styles/input.css', './index.html']).on('change', () => {
    console.log('Change detected, rebuilding...');
    build().catch(console.error);
  });
} else {
  build().catch(console.error);
}