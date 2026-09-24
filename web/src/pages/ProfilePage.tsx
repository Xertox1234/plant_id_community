import { useEffect, useState, type FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import ProfileStats from '../components/profile/ProfileStats';
import { fetchProfile, updateProfile } from '../services/profileService';
import type { ProfileUpdate, UserProfile } from '../types/auth';

type EditableField = keyof Required<ProfileUpdate>;

const EMPTY_FORM: Required<ProfileUpdate> = {
  first_name: '',
  last_name: '',
  bio: '',
  location: '',
  website: '',
};

function formFrom(profile: UserProfile): Required<ProfileUpdate> {
  return {
    first_name: profile.first_name ?? '',
    last_name: profile.last_name ?? '',
    bio: profile.bio ?? '',
    location: profile.location ?? '',
    website: profile.website ?? '',
  };
}

/**
 * ProfilePage: view and edit the signed-in user's own profile.
 *
 * Edits go to PATCH /api/v1/auth/user/update/ (web dead-code audit M3: that
 * endpoint existed and only mobile used it; this page used to say "Coming
 * Soon"). Email is shown read-only on purpose. Changing it needs
 * re-verification, which the backend does not do yet.
 */
/**
 * Keyed on the signed-in user (docs/rules/react.md): an account switch
 * remounts the form AND the stats, so a save can never diff against the
 * previous account's profile (PR #821 review).
 */
export default function ProfilePage() {
  const { user } = useAuth();
  return <ProfilePageContent key={user?.id} />;
}

function ProfilePageContent() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [form, setForm] = useState<Required<ProfileUpdate>>(EMPTY_FORM);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchProfile()
      .then((loaded) => {
        if (cancelled) return;
        setProfile(loaded);
        setForm(formFrom(loaded));
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : 'Could not load your profile.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setField = (field: EditableField) => (value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setStatus(null);
  };

  const changes: ProfileUpdate = {};
  if (profile) {
    const saved = formFrom(profile);
    (Object.keys(form) as EditableField[]).forEach((field) => {
      if (form[field] !== saved[field]) changes[field] = form[field];
    });
  }
  const dirty = Object.keys(changes).length > 0;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!dirty || saving) return;
    setSaving(true);
    setStatus(null);
    try {
      const updated = await updateProfile(changes);
      setProfile(updated);
      setForm(formFrom(updated));
      setStatus({ kind: 'ok', text: 'Profile saved.' });
      // Deliberately NOT refreshUser(): it sets the user to null when its
      // fetch fails, so a network blip after a successful save would render
      // the app signed out (todo 310). The header's name catches up on the
      // next load.
    } catch (error: unknown) {
      setStatus({
        kind: 'error',
        text: error instanceof Error ? error.message : 'Could not save your profile.',
      });
    } finally {
      setSaving(false);
    }
  };

  const name = profile?.display_name || user?.name || user?.email || '';

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-ink">Profile</h1>
        <p className="mt-2 text-ink-2">Manage your account information</p>
      </div>

      <div className="bg-surface-2 shadow-sm border border-line rounded-lg p-8">
        <div className="flex items-center gap-6 mb-8">
          <div
            aria-hidden="true"
            className="w-24 h-24 rounded-full bg-primary text-on-primary flex items-center justify-center text-3xl font-bold"
          >
            {name.substring(0, 2).toUpperCase() || 'U'}
          </div>
          <div>
            <h2 className="text-2xl font-bold text-ink">{name}</h2>
            <p className="text-ink-2">{profile?.email ?? user?.email}</p>
          </div>
        </div>

        {loadError ? (
          <p role="alert" className="text-error">
            {loadError}
          </p>
        ) : !profile ? (
          <p className="text-ink-3">Loading your profile…</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                name="first_name"
                label="First name"
                value={form.first_name}
                maxLength={150}
                onChange={(e) => setField('first_name')(e.target.value)}
              />
              <Input
                name="last_name"
                label="Last name"
                value={form.last_name}
                maxLength={150}
                onChange={(e) => setField('last_name')(e.target.value)}
              />
            </div>

            <div>
              <label htmlFor="bio" className="block text-sm font-medium text-ink-2 mb-1">
                Bio
              </label>
              <textarea
                id="bio"
                name="bio"
                rows={4}
                maxLength={500}
                value={form.bio}
                onChange={(e) => setField('bio')(e.target.value)}
                className="w-full rounded-lg border border-line bg-surface p-3 text-ink"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                name="location"
                label="Location"
                value={form.location}
                maxLength={100}
                onChange={(e) => setField('location')(e.target.value)}
              />
              <Input
                name="website"
                type="url"
                label="Website"
                value={form.website}
                placeholder="https://"
                onChange={(e) => setField('website')(e.target.value)}
              />
            </div>

            <div>
              <p className="block text-sm font-medium text-ink-2 mb-1">Email address</p>
              <p className="text-ink">{profile.email}</p>
            </div>

            <div className="flex items-center gap-4">
              <Button type="submit" loading={saving} loadingText="Saving…" disabled={!dirty}>
                Save changes
              </Button>
              <p
                aria-live="polite"
                className={status?.kind === 'error' ? 'text-sm text-error' : 'text-sm text-ink-2'}
              >
                {status?.text}
              </p>
            </div>
          </form>
        )}
      </div>

      <ProfileStats />
    </div>
  );
}
