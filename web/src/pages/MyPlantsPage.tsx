/**
 * MyPlantsPage Component
 *
 * Authenticated page listing the plants the user saved to their collection
 * after an identification ("Save to My Collection" on the identify flow).
 * Read surface for GET /api/v1/plant-identification/plants/ (todo 243).
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Leaf } from 'lucide-react';
import Card from '../components/ui/Card';
import { Pagination } from '../components/ui/Pagination';
import { plantIdService } from '../services/plantIdService';
import { logger } from '../utils/logger';
import type { UserPlant } from '../types/plantId';

const PAGE_SIZE = 20; // Backend DRF PageNumberPagination page size

interface StaticPillProps {
  children: React.ReactNode;
  tone?: string;
  suffix?: string;
}

function StaticPill({ children, tone = 'text-ink-2', suffix }: StaticPillProps) {
  return (
    <span
      className={`shrink-0 rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-micro ${tone}`}
    >
      {children}
      {suffix && <span className="sr-only"> {suffix}</span>}
    </span>
  );
}

export default function MyPlantsPage() {
  const [plants, setPlants] = useState<UserPlant[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalCount, setTotalCount] = useState<number>(0);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  const loadPlants = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await plantIdService.getMyPlants(currentPage);

      setPlants(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err) {
      logger.error('[MyPlantsPage] Failed to load plants:', err);
      setError(err instanceof Error ? err.message : 'Failed to load your plants');
    } finally {
      setLoading(false);
    }
  }, [currentPage]);

  useEffect(() => {
    loadPlants();
  }, [loadPlants]);

  return (
    <div className="flex flex-col gap-8 py-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-ink">My Plants</h1>
        <p className="mt-2 text-ink-2">
          Plants you saved to your collection after identifying them
        </p>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
          <p className="mt-4 text-ink-2">Loading your plants...</p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="bg-error/10 border border-error/30 rounded-md p-6 text-center">
          <h3 className="text-lg font-semibold text-error mb-2">Failed to Load Your Plants</h3>
          <p className="text-error mb-4">{error}</p>
          <button
            onClick={loadPlants}
            className="inline-flex items-center px-4 py-2 bg-error text-on-error rounded-md hover:bg-error/90 transition-colors"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && plants.length === 0 && (
        <Card className="p-12 text-center">
          <Leaf className="w-16 h-16 text-ink-3 mx-auto mb-4" aria-hidden="true" />
          <h3 className="text-lg font-semibold text-ink mb-2">No Plants Yet</h3>
          <p className="text-ink-2 mb-6">
            Identify a plant and save it to your collection to see it here
          </p>
          <Link
            to="/identify"
            className="inline-flex items-center px-4 py-2 bg-clay text-on-clay rounded-md hover:bg-clay/90 transition-colors"
          >
            Identify a Plant
          </Link>
        </Card>
      )}

      {/* Plants Grid */}
      {!loading && !error && plants.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {plants.map((plant) => {
              const commonNames = plant.care_instructions_json?.common_names;
              const watering = plant.care_instructions_json?.watering;
              const confidence = plant.care_instructions_json?.confidence;

              return (
                <Card key={plant.id} className="overflow-hidden">
                  {/* Image or placeholder */}
                  {plant.image_thumbnail ? (
                    <img
                      src={plant.image_thumbnail}
                      alt={plant.display_name || plant.nickname || 'Saved plant'}
                      className="w-full h-40 object-cover"
                    />
                  ) : (
                    <div className="w-full h-40 bg-primary/10 flex items-center justify-center">
                      <Leaf className="w-12 h-12 text-primary" aria-hidden="true" />
                    </div>
                  )}

                  <div className="p-5">
                    <div className="flex items-start justify-between gap-2">
                      <h2 className="text-lg font-semibold text-ink">
                        {plant.display_name || plant.nickname || 'Unnamed plant'}
                      </h2>
                      {typeof confidence === 'number' && (
                        <StaticPill tone="text-primary" suffix="match">
                          {Math.round(confidence * 100)}%
                        </StaticPill>
                      )}
                    </div>

                    {Array.isArray(commonNames) && commonNames.length > 0 && (
                      <p className="mt-1 text-sm text-ink-2">{commonNames.join(', ')}</p>
                    )}

                    {watering && (
                      <p className="mt-3 text-sm text-ink-2 line-clamp-2">
                        <span className="font-medium text-ink">Watering:</span> {watering}
                      </p>
                    )}

                    {plant.notes && (
                      <p className="mt-2 text-sm text-ink-3 line-clamp-2">{plant.notes}</p>
                    )}

                    {plant.created_at && (
                      <div className="mt-3">
                        <StaticPill>
                          Saved {new Date(plant.created_at).toLocaleDateString()}
                        </StaticPill>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <Pagination
              page={currentPage}
              onPageChange={setCurrentPage}
              hasPrevious={currentPage > 1}
              hasNext={currentPage < totalPages}
              totalPages={totalPages}
            />
          )}
        </>
      )}
    </div>
  );
}
