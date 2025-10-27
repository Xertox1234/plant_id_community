import { Link } from 'react-router-dom'

/**
 * HomePage Component
 *
 * Landing page with hero section and feature cards.
 * Header and navigation now handled by RootLayout.
 */
export default function HomePage() {
  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-green-50 to-emerald-50 py-24 px-4">
        <div className="max-w-7xl mx-auto text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            Discover the World of{' '}
            <span className="bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
              Plants
            </span>
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
            Join our community of plant enthusiasts. Identify plants with AI, 
            share your garden, and learn from experts and fellow plant lovers.
          </p>
          
          <div className="flex gap-4 justify-center">
            <Link
              to="/identify"
              className="px-8 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
            >
              Identify Plant
            </Link>
            <Link
              to="/forum"
              className="px-8 py-3 bg-white text-green-600 rounded-lg font-medium border-2 border-green-600 hover:bg-green-50 transition-colors"
            >
              Join Community
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Everything you need to explore plants
            </h2>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              From AI-powered identification to community knowledge sharing
            </p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard
              title="AI Plant Identification"
              description="Upload photos of plants and get instant identification using advanced AI technology."
              href="/identify"
            />
            <FeatureCard
              title="Discussion Forum"
              description="Ask questions, share tips, and participate in discussions about plant care."
              href="/forum"
            />
            <FeatureCard
              title="Plant Blog"
              description="Read expert articles, care guides, and plant stories from our community."
              href="/blog"
            />
          </div>
        </div>
      </section>
    </div>
  )
}

function FeatureCard({ title, description, href }) {
  return (
    <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-200 hover:shadow-md transition-shadow">
      <h3 className="text-xl font-semibold text-gray-900 mb-3">{title}</h3>
      <p className="text-gray-600 mb-6 leading-relaxed">{description}</p>
      <Link
        to={href}
        className="inline-flex items-center font-medium text-green-600 hover:underline"
      >
        Learn more →
      </Link>
    </div>
  )
}
