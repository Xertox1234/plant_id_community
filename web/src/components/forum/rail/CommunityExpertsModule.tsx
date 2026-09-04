import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users } from 'lucide-react';
import RailModule from '../../ui/RailModule';
import { fetchExperts } from '../../../services/forumService';
import { specimenAvatar } from '../../../utils/forumAvatars';
import { userProfilePath } from '../../../utils/forumUrls';
import { TRUST_LEVEL_LABELS } from '../../../utils/forumAuthor';
import { logger } from '../../../utils/logger';
import type { ForumExpert } from '@/types';
import { AVATAR_BOX, AVATAR_RADIUS } from '../../ui/dimensions';

/**
 * Right-rail module: highest-trust community members.
 *
 * Title and presence dot both key off `expert.online` (todo 301), a plain
 * truthy check — `undefined` (field absent: server predates todo 301, or any
 * other client/server skew) and `false` both read as "not online": no dot,
 * no "online" claim in the title. See ForumExpert.online's comment in
 * types/forum.ts.
 */
export default function CommunityExpertsModule() {
  const [experts, setExperts] = useState<ForumExpert[]>([]);

  useEffect(() => {
    let ignore = false;
    fetchExperts()
      .then((rows) => {
        if (!ignore) setExperts(rows);
      })
      .catch((err) => {
        logger.error('Error loading experts rail', {
          component: 'CommunityExpertsModule',
          error: err,
        });
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (experts.length === 0) return null;

  const hasOnlineExpert = experts.some((expert) => expert.online);

  return (
    <RailModule
      icon={<Users aria-hidden="true" />}
      title={hasOnlineExpert ? 'Experts online' : 'Community experts'}
    >
      <ul className="flex flex-col gap-3">
        {experts.map((expert) => (
          <li key={expert.username}>
            <Link to={userProfilePath(expert.username)} className="group flex items-center gap-2.5">
              <span className="relative inline-block shrink-0">
                <img
                  src={expert.avatar ?? specimenAvatar(expert.username)}
                  alt=""
                  className={`${AVATAR_BOX.sm} ${AVATAR_RADIUS.sm} object-cover`}
                />
                {expert.online && (
                  <span
                    className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-ok ring-2 ring-surface"
                    aria-hidden="true"
                  />
                )}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[12.5px] font-semibold text-ink transition-colors group-hover:text-primary">
                  {expert.display_name}
                  {/* The dot above is aria-hidden — without this, a
                      screen-reader user hears the module title flip to
                      "Experts online" but has no way to tell which row(s)
                      (code review). Placed after the name so it reads
                      "Iris Delgado (online)", not before it. */}
                  {expert.online && <span className="sr-only"> (online)</span>}
                </span>
                <span className="gt-label block normal-case tracking-normal">
                  {expert.title || TRUST_LEVEL_LABELS[expert.trust_level ?? 0] || 'Member'}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </RailModule>
  );
}
