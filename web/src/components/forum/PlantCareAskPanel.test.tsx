import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import PlantCareAskPanel from './PlantCareAskPanel';
import * as forumService from '../../services/forumService';
import { logger } from '../../utils/logger';
import type { PlantCareAnswer } from '../../types/forum';

/**
 * PlantCareAskPanel (todo 289 / M13) — the opt-in "ask about plant care" panel.
 *
 * Provenance-forward by design (design doc guardrail 4): every `[n]` links to
 * the cited passage, sources carry kind + title + date, the answer is labelled
 * as community content, and "this is wrong" is one click away (guardrail 5).
 * Availability follows the compose-assist contract: 401/403/`disabled` latch
 * for the session (in the service, so a remount cannot re-offer the action);
 * `unavailable`/429 are transient and keep the form usable.
 */

const ANSWERED: PlantCareAnswer = {
  status: 'answered',
  answer_id: 123,
  answer:
    'Water only when the top inch is dry [1]. Yellow lower leaves usually mean overwatering [2].',
  citations: [1, 2],
  sources: [
    {
      n: 1,
      kind: 'blog',
      title: 'Killed by kindness',
      date: '2026-05-01',
      snippet: 'Roots respire…',
      slug: 'killed-by-kindness',
      anchor: 'block-7',
    },
    {
      n: 2,
      kind: 'topic',
      title: 'Pothos leaves yellowing',
      date: '2026-06-02T14:03:00+00:00',
      snippet: 'My pothos has…',
      topic_id: 55,
      topic_slug: 'pothos-leaves-yellowing',
      board_id: 3,
      board_slug: 'care',
    },
  ],
  disclaimer: 'Assembled from this community’s blog and forum posts — not expert advice.',
};

function renderPanel(props: { initialQuestion?: string } = {}) {
  return render(
    <MemoryRouter>
      <PlantCareAskPanel {...props} />
    </MemoryRouter>
  );
}

async function openAndAsk(question = 'how often should I water a pothos') {
  await userEvent.click(screen.getByRole('button', { name: /ask about plant care/i }));
  const box = screen.getByLabelText('Your question');
  await userEvent.clear(box);
  await userEvent.type(box, question);
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
}

describe('PlantCareAskPanel', () => {
  beforeEach(() => {
    // The unavailability latch is session-scoped module state in forumService
    // (deliberately), so a 403 case would otherwise disable every later case.
    forumService.resetPlantCareAskAvailability();
    vi.spyOn(logger, 'error').mockImplementation(() => {});
  });

  it('is collapsed by default, shows the disclosure, and calls nothing until Ask', async () => {
    const ask = vi.spyOn(forumService, 'askPlantCare');
    renderPanel();
    expect(screen.getByText(/assembled only from this site/i)).toBeInTheDocument();
    expect(screen.getByText(/not expert advice/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('Your question')).not.toBeInTheDocument();
    const toggle = screen.getByRole('button', { name: /ask about plant care/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByLabelText('Your question')).toBeInTheDocument();
    expect(ask).not.toHaveBeenCalled();
  });

  it('prefills the question from initialQuestion but never auto-submits', async () => {
    const ask = vi.spyOn(forumService, 'askPlantCare');
    renderPanel({ initialQuestion: 'pothos yellow leaves' });
    await userEvent.click(screen.getByRole('button', { name: /ask about plant care/i }));
    expect(screen.getByLabelText('Your question')).toHaveValue('pothos yellow leaves');
    expect(ask).not.toHaveBeenCalled();
  });

  it('renders an answered result with citation links, kind/date sources and the label', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockResolvedValue(ANSWERED);
    renderPanel();
    await openAndAsk();

    expect(await screen.findByText(/Water only when the top inch is dry/)).toBeInTheDocument();
    // [n] markers become links to the cited passage — blog anchor, thread path.
    expect(screen.getByRole('link', { name: 'Source 1: Killed by kindness' })).toHaveAttribute(
      'href',
      '/blog/killed-by-kindness#block-7'
    );
    expect(screen.getByRole('link', { name: 'Source 2: Pothos leaves yellowing' })).toHaveAttribute(
      'href',
      '/forum/3-care/55-pothos-leaves-yellowing'
    );
    // Provenance list: kind pill + title + date, in citation order.
    const sources = screen.getByRole('list', { name: 'Sources' });
    const items = within(sources).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('Blog article');
    expect(items[0]).toHaveTextContent('Killed by kindness');
    expect(items[1]).toHaveTextContent('Forum thread');
    expect(items[1]).toHaveTextContent('Pothos leaves yellowing');
    expect(within(items[0]).getByRole('link', { name: 'Killed by kindness' })).toHaveAttribute(
      'href',
      '/blog/killed-by-kindness#block-7'
    );
    expect(screen.getByText(ANSWERED.disclaimer)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /this is wrong/i })).toBeInTheDocument();
  });

  it('renders no_information copy with no sources and no report button', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockResolvedValue({
      status: 'no_information',
      answer_id: null,
      sources: [],
    });
    renderPanel();
    await openAndAsk();
    expect(await screen.findByText(/doesn.t have anything close enough/i)).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Sources' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /this is wrong/i })).not.toBeInTheDocument();
  });

  it.each(['ingestion', 'chemical_dosing'] as const)(
    'renders the static referral for a blocked %s question, with no sources',
    async (reason) => {
      vi.spyOn(forumService, 'askPlantCare').mockResolvedValue({
        status: 'referral',
        answer_id: null,
        referral: { reason, message: `Referral copy for ${reason}.` },
      });
      renderPanel();
      await openAndAsk('is pothos toxic to cats');
      expect(await screen.findByText(`Referral copy for ${reason}.`)).toBeInTheDocument();
      expect(screen.queryByRole('list', { name: 'Sources' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /this is wrong/i })).not.toBeInTheDocument();
    }
  );

  it('renders passages_only as a sources list with no answer text and no report button', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockResolvedValue({
      status: 'passages_only',
      answer_id: null,
      sources: ANSWERED.sources,
      disclaimer: ANSWERED.disclaimer,
    });
    renderPanel();
    await openAndAsk();
    expect(await screen.findByText(/no confident answer/i)).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Sources' })).toBeInTheDocument();
    expect(screen.queryByText(/Water only when/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /this is wrong/i })).not.toBeInTheDocument();
  });

  it('disables the form and explains premium on a 403, and survives a remount', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockRejectedValue(
      new forumService.RagError(403, 'This feature requires a premium account.')
    );
    const first = renderPanel();
    await openAndAsk();
    expect(await screen.findByText(/requires a premium account/i)).toBeInTheDocument();
    // Disabled but still MOUNTED so the focus the user just placed isn't dropped.
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
    expect(forumService.isPlantCareAskUnavailable()).toBe(true);
    first.unmount();

    renderPanel();
    await userEvent.click(screen.getByRole('button', { name: /ask about plant care/i }));
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
  });

  it('asks the visitor to sign in on a 401 and latches', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockRejectedValue(
      new forumService.RagError(401, 'Authentication credentials were not provided.')
    );
    renderPanel();
    await openAndAsk();
    expect(await screen.findByText(/sign in/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
    expect(forumService.isPlantCareAskUnavailable()).toBe(true);
  });

  it('disables the form on a 503 that means the feature is off', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockRejectedValue(
      new forumService.RagError(503, 'Plant-care answers are not enabled.', 'disabled')
    );
    renderPanel();
    await openAndAsk();
    expect(await screen.findByText(/not enabled/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
    expect(forumService.isPlantCareAskUnavailable()).toBe(true);
  });

  it('keeps the form usable after a TRANSIENT 503 (provider or retrieval blip)', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockRejectedValue(
      new forumService.RagError(503, 'Plant-care answers are unavailable right now.', 'unavailable')
    );
    renderPanel();
    await openAndAsk();
    expect(await screen.findByText(/unavailable right now/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask' })).toBeEnabled();
    expect(forumService.isPlantCareAskUnavailable()).toBe(false);
  });

  it('keeps the form usable after a 429', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockRejectedValue(
      new forumService.RagError(429, 'Plant-care answers are temporarily at capacity.')
    );
    renderPanel();
    await openAndAsk();
    expect(await screen.findByText(/at capacity/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask' })).toBeEnabled();
    expect(forumService.isPlantCareAskUnavailable()).toBe(false);
  });

  it('reports non-optimistically: confirmation only after the request resolves', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockResolvedValue(ANSWERED);
    let resolveReport: () => void = () => {};
    const report = vi
      .spyOn(forumService, 'reportPlantCareAnswer')
      .mockImplementation(() => new Promise<void>((resolve) => (resolveReport = resolve)));
    renderPanel();
    await openAndAsk();
    await screen.findByText(/Water only when/);

    await userEvent.click(screen.getByRole('button', { name: /this is wrong/i }));
    await userEvent.type(
      screen.getByLabelText(/what is wrong/i),
      'Pothos should not be watered daily'
    );
    await userEvent.click(screen.getByRole('button', { name: 'Submit report' }));

    expect(report).toHaveBeenCalledWith(123, 'Pothos should not be watered daily');
    // Still in flight → no confirmation yet.
    expect(screen.queryByText(/reported — thanks/i)).not.toBeInTheDocument();
    resolveReport();
    expect(await screen.findByText(/reported — thanks/i)).toBeInTheDocument();
  });

  it('keeps the report form open and shows the error when the report fails', async () => {
    vi.spyOn(forumService, 'askPlantCare').mockResolvedValue(ANSWERED);
    vi.spyOn(forumService, 'reportPlantCareAnswer').mockRejectedValue(
      new forumService.ForumApiError('Request failed', 500)
    );
    renderPanel();
    await openAndAsk();
    await screen.findByText(/Water only when/);
    await userEvent.click(screen.getByRole('button', { name: /this is wrong/i }));
    await userEvent.click(screen.getByRole('button', { name: 'Submit report' }));
    expect(await screen.findByText(/could not send your report/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Submit report' })).toBeInTheDocument();
    expect(screen.queryByText(/reported — thanks/i)).not.toBeInTheDocument();
  });

  it('caps the question at 500 characters', async () => {
    renderPanel();
    await userEvent.click(screen.getByRole('button', { name: /ask about plant care/i }));
    expect(screen.getByLabelText('Your question')).toHaveAttribute('maxLength', '500');
    await waitFor(() => expect(screen.getByText('0/500')).toBeInTheDocument());
  });
});
