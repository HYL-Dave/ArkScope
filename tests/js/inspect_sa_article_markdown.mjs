import fs from 'node:fs';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {JSDOM} from 'jsdom';

const source = fs.readFileSync(0, 'utf8');
const html = renderToStaticMarkup(createElement(ReactMarkdown, {remarkPlugins:[remarkGfm]}, source));
const dom = new JSDOM(html);
const doc = dom.window.document;
process.stdout.write(JSON.stringify({
  links:[...doc.querySelectorAll('a')].map(node=>({text:node.textContent,href:node.getAttribute('href')})),
  images:[...doc.querySelectorAll('img')].map(node=>({src:node.getAttribute('src'),alt:node.alt,title:node.title})),
  tables:[...doc.querySelectorAll('table')].map(table=>[...table.rows].map(row=>[...row.cells].map(cell=>cell.textContent))),
}));
dom.window.close();
