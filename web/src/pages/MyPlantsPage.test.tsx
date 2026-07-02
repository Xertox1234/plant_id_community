/**
 * MyPlantsPage Tests
 *
 * Covers the read surface for the user's saved plant collection (todo 243):
 * loading, list rendering, empty state with identify CTA, error state with
 * retry, and pagination.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import MyPlantsPage from './MyPlantsPage';
import type { PaginatedUserPlants, UserPlant } from '../types/plantId';

const { getMyPlantsMock } = vi.hoisted(() => ({
  getMyPlantsMock: vi.fn(),
}));

vi.mock('../services/plantIdService', () => ({
  plantIdService: {
    getMyPlants: getMyPlantsMock,
  },
}));

vi.mock('../utils/logger', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

const makePlant = (overrides: Partial<UserPlant> = {}): UserPlant => ({
  id: 'plant-1',
  collection: 'collection-1',
  nickname: 'Rosa damascena',
  notes: '',
  care_instructions_json: {
    confidence: 0.97,
    common_names: ['Damask Rose'],
    watering: 'Water weekly',
    source: 'plant_id',
  },
  created_at: '2026-01-15T00:00:00Z',
  ...overrides,
});

const makeResponse = (overrides: Partial<PaginatedUserPlants> = {}): PaginatedUserPlants => ({
  count: 1,
  next: null,
  previous: null,
  results: [makePlant()],
  ...overrides,
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <MyPlantsPage />
    </MemoryRouter>
  );

describe('MyPlantsPage', () => {
  beforeEach(() => {
    getMyPlantsMock.mockReset();
  });

  it('shows a loading state while plants are being fetched', () => {
    getMyPlantsMock.mockReturnValue(new Promise(() => {})); // never resolves

    renderPage();

    expect(screen.getByText('Loading your plants...')).toBeInTheDocument();
  });

  it('renders saved plants with name, common names, and confidence', async () => {
    getMyPlantsMock.mockResolvedValue(
      makeResponse({
        count: 2,
        results: [
          makePlant(),
          makePlant({
            id: 'plant-2',
            nickname: 'Monstera deliciosa',
            care_instructions_json: { confidence: 0.81, common_names: ['Swiss Cheese Plant'] },
          }),
        ],
      })
    );

    renderPage();

    expect(await screen.findByText('Rosa damascena')).toBeInTheDocument();
    expect(screen.getByText('Monstera deliciosa')).toBeInTheDocument();
    expect(screen.getByText('Damask Rose')).toBeInTheDocument();
    expect(screen.getByText('97% match')).toBeInTheDocument();
    expect(screen.getByText('81% match')).toBeInTheDocument();
    expect(getMyPlantsMock).toHaveBeenCalledWith(1);
  });

  it('prefers display_name over nickname when present', async () => {
    getMyPlantsMock.mockResolvedValue(
      makeResponse({
        results: [makePlant({ display_name: 'Bedroom Rose' })],
      })
    );

    renderPage();

    expect(await screen.findByText('Bedroom Rose')).toBeInTheDocument();
    expect(screen.queryByText('Rosa damascena')).not.toBeInTheDocument();
  });

  it('shows the empty state with an identify link when no plants are saved', async () => {
    getMyPlantsMock.mockResolvedValue(makeResponse({ count: 0, results: [] }));

    renderPage();

    expect(await screen.findByText('No Plants Yet')).toBeInTheDocument();
    const identifyLink = screen.getByRole('link', { name: 'Identify a Plant' });
    expect(identifyLink).toHaveAttribute('href', '/identify');
  });

  it('shows the error state and retries on Try Again', async () => {
    getMyPlantsMock
      .mockRejectedValueOnce(new Error('Authentication required to view your plants'))
      .mockResolvedValueOnce(makeResponse());

    renderPage();

    expect(
      await screen.findByText('Authentication required to view your plants')
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Try Again' }));

    expect(await screen.findByText('Rosa damascena')).toBeInTheDocument();
    expect(getMyPlantsMock).toHaveBeenCalledTimes(2);
  });

  it('paginates: Next requests the following page', async () => {
    getMyPlantsMock
      .mockResolvedValueOnce(
        makeResponse({
          count: 25,
          next: 'next-url',
          results: [makePlant()],
        })
      )
      .mockResolvedValueOnce(
        makeResponse({
          count: 25,
          previous: 'prev-url',
          results: [makePlant({ id: 'plant-21', nickname: 'Page two plant' })],
        })
      );

    renderPage();

    expect(await screen.findByText('Showing page 1 of 2 (25 total)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText('Page two plant')).toBeInTheDocument();
    await waitFor(() => expect(getMyPlantsMock).toHaveBeenLastCalledWith(2));
    expect(screen.getByText('Showing page 2 of 2 (25 total)')).toBeInTheDocument();
  });

  it('hides pagination when everything fits on one page', async () => {
    getMyPlantsMock.mockResolvedValue(makeResponse());

    renderPage();

    expect(await screen.findByText('Rosa damascena')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument();
  });
});
