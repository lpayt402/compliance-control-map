const ISO_DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

export function formatDateOnly(value: string | null | undefined, locale?: string): string {
  if (!value) return "—";
  const match = ISO_DATE_ONLY.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(Date.UTC(Number(year), Number(month) - 1, Number(day))));
}

const ACTION_LABELS: Record<string, string> = {
  ASSESSMENT_UPDATED: "Assessment updated",
  CONTROL_CREATED: "Control created",
  CONTROL_UPDATED: "Control updated",
  CONTROL_LINKED: "Control mapped",
  CONTROL_UNLINKED: "Control unmapped",
  DOCUMENT_MAPPED: "Document mapped",
  DOCUMENT_UNMAPPED: "Document detached",
  EVIDENCE_MAPPED: "Evidence mapped",
  EVIDENCE_UNMAPPED: "Evidence detached",
  NOTE_CREATED: "Note created",
  NOTE_UPDATED: "Note updated",
  NOTE_DELETED: "Note deleted",
  PLAYBOOK_CREATED: "Playbook created",
  PLAYBOOK_UPDATED: "Playbook updated",
  PLAYBOOK_DELETED: "Playbook deleted",
  CONTACT_CREATED: "Contact created",
  CONTACT_UPDATED: "Contact updated",
  CONTACT_DELETED: "Contact deleted",
};

export function formatActionCode(actionCode: string): string {
  if (ACTION_LABELS[actionCode]) return ACTION_LABELS[actionCode];
  const words = actionCode.replaceAll("_", " ").toLocaleLowerCase();
  return words ? words.charAt(0).toLocaleUpperCase() + words.slice(1) : "Activity item";
}
