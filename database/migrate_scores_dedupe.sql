-- Keep only the latest admin_scores row per user, then enforce one-per-user.
DELETE FROM admin_scores
WHERE id NOT IN (
    SELECT DISTINCT ON (user_id) id
    FROM admin_scores
    ORDER BY user_id, updated_at DESC NULLS LAST, id DESC
);

ALTER TABLE admin_scores
    DROP CONSTRAINT IF EXISTS uq_admin_scores_user;

ALTER TABLE admin_scores
    ADD CONSTRAINT uq_admin_scores_user UNIQUE (user_id);
