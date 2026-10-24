const http = require('http');

const routes = [
  '/',
  '/trips',
  '/trips/new',
  '/trains',
  '/booking',
  '/history',
  '/settings',
  '/threeui-preview',
  '/landing-pages/meng-to-sketchbook.html',
];

async function checkRoute(route) {
  return new Promise((resolve) => {
    http.get(`http://localhost:3001${route}`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({
          route,
          status: res.statusCode,
          length: data.length,
          hasTitle: data.includes('Tatkal Assistant') || data.includes('Meng To') || data.includes('<html'),
        });
      });
    }).on('error', (err) => {
      resolve({ route, status: 'ERROR', error: err.message });
    });
  });
}

(async () => {
  console.log('\n--- VERIFYING LIVE HTTP ROUTES (http://localhost:3001) ---');
  let allOk = true;
  for (const r of routes) {
    const res = await checkRoute(r);
    console.log(`Route: ${res.route.padEnd(40)} | Status: ${res.status} | Length: ${res.length} bytes | OK: ${res.hasTitle}`);
    if (res.status !== 200) allOk = false;
  }
  console.log('All routes verified OK:', allOk);
})();
