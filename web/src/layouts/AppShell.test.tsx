import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../contexts/ThemeContext';
import AppShell from './AppShell';
import RailSlot, { RAIL_MEDIA_QUERY } from '../components/layout/RailSlot';
import * as notificationService from '../services/notificationService';
import * as messageService from '../services/messageService';

const mockAuth = {
  isAuthenticated: false,
  user: null as { username?: string } | null,
  logout: vi.fn(),
};
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => mockAuth }));
vi.mock('../services/notificationService', () => ({
  fetchUnreadCount: vi.fn(),
  fetchNotifications: vi.fn(),
  markNotificationsRead: vi.fn(),
}));
vi.mock('../services/messageService', () => ({
  fetchUnreadConversationCount: vi.fn(),
}));
vi.mock('../components/layout/NotificationBell', () => ({
  default: () => <div data-testid="notification-bell" />,
}));
// The real UserMenu trigger also carries data-testid="user-menu" (todo 312) —
// this mock's testid isn't a stand-in for a nonexistent one anymore, it's just
// keeping this suite from depending on UserMenu's internals.
vi.mock('../components/layout/UserMenu', () => ({
  default: () => <div data-testid="user-menu" />,
}));
// AppShell's own wiring (open state + keyboard shortcut + pill) is under
// test here; CommandPalette's internals (search, keyboard nav, sections)
// have their own dedicated suite in CommandPalette.test.tsx.
vi.mock('../components/CommandPalette', () => ({
  default: ({ open }: { open: boolean }) =>
    open ? <div role="dialog" aria-label="Search" data-testid="command-palette" /> : null,
}));

const renderShell = (children: React.ReactNode = <p>page body</p>) =>
  render(
    <ThemeProvider>
      <MemoryRouter>
        <AppShell>{children}</AppShell>
      </MemoryRouter>
    </ThemeProvider>
  );

beforeEach(() => {
  mockAuth.isAuthenticated = false;
  mockAuth.logout = vi.fn();
  localStorage.clear();
  delete document.documentElement.dataset.mode;
  vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(0);
  vi.mocked(messageService.fetchUnreadConversationCount).mockResolvedValue(0);
  vi.mocked(notificationService.fetchNotifications).mockResolvedValue({
    results: [],
    next: null,
    previous: null,
  });
  vi.mocked(notificationService.markNotificationsRead).mockResolvedValue(0);
});

describe('AppShell', () => {
  it('renders brand, nav, search, and the page body', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Houseplant MD home' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /search plants, posts, people/i })
    ).toBeInTheDocument();
    expect(screen.getByText('page body')).toBeInTheDocument();
    expect(document.getElementById('main-content')).not.toBeNull();
  });
  it('shows Sign up and Log in when logged out', () => {
    renderShell();
    expect(screen.getByRole('link', { name: 'Sign up' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument();
  });
  it('RailSlot portals page content into the rail', () => {
    // RailSlot mounts its children only when the xl rail query matches — the
    // global setup.ts polyfill always reports false, so stub matchMedia
    // (defined writable there) for the wide-viewport behavior, then restore.
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query === RAIL_MEDIA_QUERY,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    try {
      renderShell(
        <RailSlot>
          <p>rail content</p>
        </RailSlot>
      );
      const rail = document.getElementById('app-rail');
      expect(rail).not.toBeNull();
      expect(rail).toHaveTextContent('rail content');
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('RailSlot mounts nothing below the xl breakpoint', () => {
    // Default polyfill: every query reports false → the hidden rail's
    // children (and their data fetches) must not mount at all.
    renderShell(
      <RailSlot>
        <p>rail content</p>
      </RailSlot>
    );
    expect(document.getElementById('app-rail')).not.toHaveTextContent('rail content');
  });

  it('drawer opens and closes', async () => {
    renderShell();
    const trigger = screen.getByRole('button', { name: 'Open menu' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(2);

    await userEvent.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(1);
  });

  it('drawer closes on nav item click', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const [, drawerNav] = screen.getAllByRole('navigation', { name: 'Main' });
    await userEvent.click(within(drawerNav).getByRole('link', { name: 'Blog' }));

    expect(screen.getAllByRole('navigation', { name: 'Main' })).toHaveLength(1);
  });

  it('theme toggle flips mode', async () => {
    renderShell();
    const toggle = screen.getByRole('button', { name: /switch to light mode/i });
    expect(toggle).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(toggle);
    const flipped = screen.getByRole('button', { name: /switch to dark mode/i });
    expect(flipped).toHaveAttribute('aria-pressed', 'false');
    expect(document.documentElement).toHaveAttribute('data-mode', 'light');
  });

  it('renders authenticated topbar', () => {
    mockAuth.isAuthenticated = true;
    renderShell();
    expect(screen.getByTestId('notification-bell')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Messages' })).toHaveAttribute('href', '/messages');
    expect(screen.getByTestId('user-menu')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign up' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /log in/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument();
  });

  it('wires the logout button to AuthContext logout', async () => {
    mockAuth.isAuthenticated = true;
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: /log out/i }));
    expect(mockAuth.logout).toHaveBeenCalledTimes(1);
  });

  it('Escape closes the open drawer', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
  });

  it('clicking the drawer brand link closes the drawer', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const dialog = screen.getByRole('dialog', { name: 'Menu' });
    await userEvent.click(within(dialog).getByRole('link', { name: 'Houseplant MD home' }));

    expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
  });

  // --- drawer focus trap (todo 400) -------------------------------------------

  it('drawer: Tab from the last control wraps to the first instead of leaving', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    const dialog = screen.getByRole('dialog', { name: 'Menu' });
    within(dialog)
      .getByRole('link', { name: /log in/i })
      .focus();

    await userEvent.tab();
    expect(within(dialog).getByRole('link', { name: 'Houseplant MD home' })).toHaveFocus();
  });

  it('drawer: Shift+Tab from the first control wraps to the last', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    const dialog = screen.getByRole('dialog', { name: 'Menu' });
    within(dialog).getByRole('link', { name: 'Houseplant MD home' }).focus();

    await userEvent.tab({ shift: true });
    expect(within(dialog).getByRole('link', { name: /log in/i })).toHaveFocus();
  });

  it('drawer: focus moves to Close menu on open and back to Open menu on Escape', async () => {
    renderShell();
    const trigger = screen.getByRole('button', { name: 'Open menu' });
    await userEvent.click(trigger);
    expect(screen.getByRole('button', { name: 'Close menu' })).toHaveFocus();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  // Tailwind's md breakpoint, pinned as a literal (todo 488): importing the
  // component's constant let a changed breakpoint stay green.
  const MD_QUERY = '(min-width: 48rem)';

  // Stub matchMedia so the md query reports `md.matches` and keeps its change
  // listeners, letting a test fire viewport transitions and count listeners.
  const stubMdMatchMedia = (initiallyMatches: boolean) => {
    const md = {
      matches: initiallyMatches,
      listeners: new Set<(e: MediaQueryListEvent) => void>(),
    };
    window.matchMedia = ((query: string) => ({
      get matches() {
        return query === MD_QUERY ? md.matches : false;
      },
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: (_type: string, cb: (e: MediaQueryListEvent) => void) => {
        if (query === MD_QUERY) md.listeners.add(cb);
      },
      removeEventListener: (_type: string, cb: (e: MediaQueryListEvent) => void) => {
        if (query === MD_QUERY) md.listeners.delete(cb);
      },
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;
    const fire = (matches: boolean) => {
      md.matches = matches;
      act(() => {
        md.listeners.forEach((cb) => cb({ matches, media: MD_QUERY } as MediaQueryListEvent));
      });
    };
    return { md, fire };
  };

  // Run every deferral (rAF or timeout, however long) that a close scheduled,
  // so a focus assertion that follows sees where focus SETTLES, not only where
  // the commit left it. A useModalFocus that restored to the trigger in a rAF
  // or a timeout would pass a synchronous check and then steal focus back from
  // <main> (todo 509). Fake timers: a real 50 ms sleep caught only deferrals
  // shorter than itself (todo 522). A caller installs vi.useFakeTimers() BEFORE
  // rendering and opens the drawer with fireEvent, not userEvent: user-event
  // runs inside RTL's asyncWrapper, whose setTimeout(0) drain is only advanced
  // under Jest fake timers, so under Vitest's it hangs until the test times
  // out. runOnlyPendingTimers, not runAllTimers: the unread-count poll is an
  // interval, which runAllTimers would spin on until Vitest aborts it.
  const flushDeferred = () =>
    act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

  it('drawer closes when the window widens past md (todo 420)', async () => {
    // At md the drawer is only display:none, so an open drawer kept its focus
    // trap (swallowing Tab) and its body scroll lock on the desktop layout.
    const originalMatchMedia = window.matchMedia;
    const { fire } = stubMdMatchMedia(false);
    try {
      vi.useFakeTimers();
      renderShell();
      const main = screen.getByRole('main');
      const focusSpy = vi.spyOn(main, 'focus');
      // Focused first, as a real click leaves it: the trigger is what
      // useModalFocus restores to on close, and that restore is the subject.
      const trigger = screen.getByRole('button', { name: 'Open menu' });
      trigger.focus();
      fireEvent.click(trigger);
      expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument();
      expect(document.body.style.overflow).toBe('hidden');

      fire(true);

      expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
      expect(document.body.style.overflow).toBe('');
      // The Open menu trigger is md:hidden at this width, so restoring focus
      // to it dropped focus to <body>; it lands on <main> instead (todo 488).
      expect(main).toHaveFocus();
      await flushDeferred();
      expect(main).toHaveFocus();
      // Without preventScroll, focusing the tall <main> can scroll the page;
      // jsdom has no layout, so pin the option itself (todo 509) -- on the ONE
      // call, after the flush. toHaveBeenCalledWith alone passed as long as any
      // call carried it, so a later bare focus() -- the call that would scroll
      // -- slipped through (todo 522).
      expect(focusSpy).toHaveBeenCalledTimes(1);
      expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
    } finally {
      vi.useRealTimers();
      window.matchMedia = originalMatchMedia;
    }
  });

  // md is already false here, so fire(false) changes no state: this guards only
  // against an inverted event.matches in useMediaQuery. The next test drives a
  // real wide-to-narrow transition (todo 509).
  it('drawer stays open when the md query changes to not matching (todo 488)', async () => {
    const originalMatchMedia = window.matchMedia;
    const { fire } = stubMdMatchMedia(false);
    try {
      renderShell();
      await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
      const closeButton = screen.getByRole('button', { name: 'Close menu' });
      expect(closeButton).toHaveFocus();

      fire(false);

      expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument();
      expect(document.body.style.overflow).toBe('hidden');
      expect(closeButton).toHaveFocus();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('drawer opens after md goes from matching to not matching (todo 509)', async () => {
    // A real true-to-false transition: if AppShell ignored it (drawerHidden
    // stuck true), the drawer would auto-close the moment it opened.
    const originalMatchMedia = window.matchMedia;
    const { fire } = stubMdMatchMedia(true);
    try {
      renderShell();
      fire(false);

      await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

      expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument();
      expect(document.body.style.overflow).toBe('hidden');
      expect(screen.getByRole('button', { name: 'Close menu' })).toHaveFocus();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('drawer opened while md already matches closes without a change event (todo 488)', async () => {
    const originalMatchMedia = window.matchMedia;
    stubMdMatchMedia(true);
    try {
      vi.useFakeTimers();
      renderShell();
      // jsdom applies no CSS, so the md:hidden trigger is still clickable.
      // Focused first, as a real click leaves it: a restore to it must not win.
      const trigger = screen.getByRole('button', { name: 'Open menu' });
      trigger.focus();
      fireEvent.click(trigger);

      expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
      expect(document.body.style.overflow).toBe('');
      expect(screen.getByRole('main')).toHaveFocus();
      await flushDeferred();
      expect(screen.getByRole('main')).toHaveFocus();
    } finally {
      vi.useRealTimers();
      window.matchMedia = originalMatchMedia;
    }
  });

  it('only the widen auto-close sends focus to main; a later Escape returns it to Open menu (todo 509)', async () => {
    // closedOnWidenRef is one-shot: without its reset, every close after one
    // widen auto-close would send focus to <main> instead of the trigger.
    const originalMatchMedia = window.matchMedia;
    const { fire } = stubMdMatchMedia(false);
    try {
      renderShell();
      const trigger = screen.getByRole('button', { name: 'Open menu' });
      const main = screen.getByRole('main');
      await userEvent.click(trigger);

      fire(true);
      expect(main).toHaveFocus();

      fire(false);
      await userEvent.click(trigger);
      expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument();
      await userEvent.keyboard('{Escape}');

      expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
      expect(trigger).toHaveFocus();
      expect(main).not.toHaveFocus();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('removes its md query listener on unmount (todo 488)', () => {
    // Relative to the listeners already there, not an absolute count: another
    // subscriber to the same query is legitimate. So AppShell must add at
    // least one listener -- not exactly 1, by todo 509's decision -- and
    // unmount must bring the count back to where it started (todo 522). The
    // bystander stands in for that other subscriber, so "back to the start"
    // is not just "zero" and AppShell's cleanup is shown to remove only its
    // own listeners.
    const originalMatchMedia = window.matchMedia;
    const { md } = stubMdMatchMedia(false);
    try {
      md.listeners.add(() => {});
      const before = md.listeners.size;
      const { unmount } = renderShell();
      expect(md.listeners.size).toBeGreaterThan(before);

      unmount();

      expect(md.listeners.size).toBe(before);
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('open drawer has dialog role with aria-modal', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));

    const dialog = screen.getByRole('dialog', { name: 'Menu' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('locks body scroll while the drawer is open and restores it after close', async () => {
    renderShell();
    expect(document.body.style.overflow).toBe('');

    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(document.body.style.overflow).toBe('hidden');

    await userEvent.click(screen.getByRole('button', { name: 'Close menu' }));
    expect(document.body.style.overflow).toBe('');
  });

  it('hides the inbox link when logged out', () => {
    renderShell();
    expect(screen.queryByRole('link', { name: /^messages/i })).not.toBeInTheDocument();
  });

  it('shows the unread-conversation badge on the inbox link (todo 339)', async () => {
    mockAuth.isAuthenticated = true;
    vi.mocked(messageService.fetchUnreadConversationCount).mockResolvedValue(2);
    renderShell();
    expect(await screen.findByRole('link', { name: 'Messages (2 unread)' })).toBeInTheDocument();
  });

  it('shows the unread count badge on the Forum nav item', async () => {
    mockAuth.isAuthenticated = true;
    vi.mocked(notificationService.fetchUnreadCount).mockResolvedValue(3);
    renderShell();
    const forumLinks = await screen.findAllByRole('link', { name: /Forum/ });
    expect(forumLinks.length).toBeGreaterThan(0);
    expect(within(forumLinks[0]).getByText('3')).toBeInTheDocument();
  });

  it('Ctrl+K opens the command palette', () => {
    renderShell();
    expect(screen.queryByTestId('command-palette')).not.toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });

    expect(screen.getByTestId('command-palette')).toBeInTheDocument();
  });

  it('Ctrl+K with the drawer open closes the drawer and opens the command palette', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: 'Open menu' }));
    expect(screen.getByRole('dialog', { name: 'Menu' })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });

    expect(screen.queryByRole('dialog', { name: 'Menu' })).not.toBeInTheDocument();
    expect(screen.getByTestId('command-palette')).toBeInTheDocument();
    // The drawer's own scroll lock must have released — otherwise the
    // shared, ref-counted lock (useBodyScrollLock) would still show
    // "hidden" here even after the drawer closed, since CommandPalette is
    // mocked in this suite and never acquires its own real lock.
    expect(document.body.style.overflow).toBe('');
  });

  it('clicking the search pill opens the command palette', async () => {
    renderShell();
    await userEvent.click(screen.getByRole('button', { name: /search plants, posts, people/i }));

    expect(screen.getByTestId('command-palette')).toBeInTheDocument();
  });
});
