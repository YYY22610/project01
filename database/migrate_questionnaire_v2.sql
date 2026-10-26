-- =============================================================================
-- 迁移：问卷结构升级（适配 2026-10-14 版实验阶段问卷）
--
-- 背景：
--   原 questionnaire_items 只有 sort_order 一个顺序维度，无法区分「前置问卷」与
--   「后置问卷」；前置问卷原先硬编码在 Consent.tsx + schemas/auth.py 的 10 个
--   具名字段里，既不能在管理后台改，也没有独立的作答记录。
--   现统一为：所有题目进 questionnaire_items，用 phase 列区分阶段，
--   作答统一进 questionnaire_responses，与后置问卷共用一套代码与导出逻辑。
--
-- 本脚本幂等：可重复执行。
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. questiontype 枚举增加 multiple（Q10 智能体认知多选）
--    注意：PostgreSQL 的 ALTER TYPE ... ADD VALUE 无法在事务块内执行，
--    需单独提交；在 PG 12+ 中可在事务内执行但新值在提交前不可用，这里保持单条执行。
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname = 'questiontype' AND e.enumlabel = 'multiple'
    ) THEN
        ALTER TYPE questiontype ADD VALUE 'multiple';
    END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- 2. phase 列：pre = 前置问卷（知情同意页），post = 后置问卷（任务完成后）
--    存量数据全部视为 post（与改造前语义一致：问卷表原本只装后置问卷）。
-- -----------------------------------------------------------------------------
ALTER TABLE questionnaire_items
    ADD COLUMN IF NOT EXISTS phase VARCHAR(10) NOT NULL DEFAULT 'post';

-- -----------------------------------------------------------------------------
-- 3. is_reverse：反向计分题标记
--    新问卷中 Q12（社会影响）、Q20（感知拟人化）、Q25（享乐动机）为反向表述，
--    聚合求均值时需做 6-x 翻转，否则会污染构念得分。
--    导出聚合按此列翻转；单题原始分仍原样保留在 questionnaire_responses 中。
-- -----------------------------------------------------------------------------
ALTER TABLE questionnaire_items
    ADD COLUMN IF NOT EXISTS is_reverse BOOLEAN NOT NULL DEFAULT FALSE;

-- -----------------------------------------------------------------------------
-- 4. section_note：题组说明（前置问卷的指导语等）
--    原文档中「以下题目测量您对……请根据您目前的真实态度作答」这类引导语，
--    放在 question_text 里会被参与者当成题干读，单独存一列由前端渲染为提示段落。
-- -----------------------------------------------------------------------------
ALTER TABLE questionnaire_items
    ADD COLUMN IF NOT EXISTS section_note TEXT;

-- -----------------------------------------------------------------------------
-- 5. 放宽 construct 长度：VARCHAR(20) 装不下新构念名
--    如 performance_expectancy(21) / resistance_intention(21) / hedonic_motivation(17)
--    加上 affective_experience(20) 已到边界，anthropomorphism(16) 尚可但后续构念
--    可能更长。统一放宽到 64，与 question_text 的 Text 类型解耦。
-- -----------------------------------------------------------------------------
ALTER TABLE questionnaire_items
    ALTER COLUMN construct TYPE VARCHAR(64);

-- -----------------------------------------------------------------------------
-- 6. phase 索引：每次取问卷都按 (phase, sort_order) 过滤排序
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_questionnaire_items_phase
    ON questionnaire_items (phase, sort_order);

-- -----------------------------------------------------------------------------
-- 7. applicable_groups 语义变更说明（不改表结构）
--    新问卷全部统一措辞（依赖指导语说明「未使用智能体助理的被试如何作答」），
--    所有题目的 applicable_groups 统一写 'ALL'，不再做 H 组改写。
--    字段保留：管理后台仍可按组过滤，且未来若要恢复分组措辞无需再迁移。
-- -----------------------------------------------------------------------------

-- 校验
SELECT phase, count(*) AS items
FROM questionnaire_items
GROUP BY phase
ORDER BY phase;
