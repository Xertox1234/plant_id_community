# Plant ID Community - Web Frontend Documentation

Welcome to the Plant ID Community web frontend documentation. This React-based web application serves as a companion to the Flutter mobile app, providing plant identification capabilities through a clean, responsive interface.

## 📚 Documentation Structure

- **[Architecture.md](./Architecture.md)** - System design, technology stack, and architectural decisions
- **[Getting-Started.md](./Getting-Started.md)** - Setup guide for new developers
- **[Components.md](./Components.md)** - Component library and usage guide
- **[API-Integration.md](./API-Integration.md)** - Backend API integration patterns
- **[Performance.md](./Performance.md)** - Image compression and optimization strategies
- **[Styling.md](./Styling.md)** - Tailwind CSS conventions and design system
- **[Testing.md](./Testing.md)** - Testing strategy and guidelines (future)
- **[Deployment.md](./Deployment.md)** - Production build and deployment guide

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

**Prerequisites:**
- Node.js 18+
- Backend running at `http://localhost:8000`
- Environment variables configured (see Getting-Started.md)

## 🏗️ Project Overview

**Technology Stack:**
- **React 19.1.1** - Latest React with concurrent rendering
- **Vite 7.1.7** - Next-generation build tool
- **Tailwind CSS 4.1.15** - Utility-first CSS framework
- **React Router 7.9.4** - Client-side routing
- **Axios 1.12.2** - HTTP client for API calls

**Key Features:**
- 🌿 AI-powered plant identification
- 📷 Client-side image compression (85% size reduction)
- 🎨 Responsive design with Tailwind CSS
- ⚡ Fast development with Vite HMR
- 🔌 Django backend integration via proxy

## 📁 Project Structure

```
web/
├── docs/                       # Documentation (you are here)
├── src/
│   ├── pages/                  # Route-based page components
│   │   ├── HomePage.jsx        # Landing page
│   │   ├── IdentifyPage.jsx    # Plant identification workflow
│   │   ├── BlogPage.jsx        # Blog (placeholder)
│   │   └── ForumPage.jsx       # Forum (placeholder)
│   ├── components/
│   │   └── PlantIdentification/
│   │       ├── FileUpload.jsx              # Image upload + compression
│   │       └── IdentificationResults.jsx   # Results display
│   ├── services/
│   │   └── plantIdService.js   # Backend API client
│   ├── utils/
│   │   └── imageCompression.js # Image optimization utility
│   ├── App.jsx                 # Router setup
│   └── main.jsx                # React entry point
├── public/                     # Static assets
├── vite.config.js              # Vite configuration
├── tailwind.config.js          # Tailwind theme
└── package.json                # Dependencies
```

## 🎯 Current Development Status

### ✅ Implemented
- Plant identification workflow (upload → identify → results)
- Client-side image compression (Week 2 optimization)
- Responsive landing page
- Backend API integration
- Error handling and loading states

### 🚧 In Progress
- User authentication
- Plant collection management
- Identification history

### 📋 Planned
- Blog integration (Wagtail CMS)
- Forum integration (Django Machina)
- User profiles
- Advanced search and filters

## 🤝 Contributing

This is the web companion to the Flutter mobile app. The mobile app is the primary platform, so web features should:

1. Match mobile functionality where appropriate
2. Leverage desktop screen space effectively
3. Maintain consistency with the design system
4. Avoid complex features better suited for mobile

## 📖 Related Documentation

- [Main Project README](../../../README.md)
- [Backend Documentation](../../../backend/README.md)
- [Flutter Mobile Documentation](../../../plant_community_mobile/README.md)
- [CLAUDE.md](../../../CLAUDE.md) - Development guide for Claude Code

## 🔗 Useful Links

- [React 19 Documentation](https://react.dev/)
- [Vite Documentation](https://vite.dev/)
- [Tailwind CSS v4](https://tailwindcss.com/)
- [React Router](https://reactrouter.com/)

---

**Last Updated:** 2025-10-22
**Maintained By:** Plant ID Community Team
