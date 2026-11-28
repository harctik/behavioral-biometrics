# AetherAuth frontend

Next.js 16, React 19 and TypeScript. Setup, configuration and the local test sign-in are described in the [project README](../README.md).

```bash
npm ci
npm run dev -- -H 127.0.0.1
npm run lint
npm run build
```

The backend address comes from `BACKEND_URL` and `NEXT_PUBLIC_API_URL`, and defaults to `http://127.0.0.1:5000`. If the backend runs anywhere else, set both.
