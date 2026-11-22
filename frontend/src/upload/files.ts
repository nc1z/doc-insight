export const MAX_FILE_COUNT = 10;
export const MAX_FILE_BYTES = 20 * 1024 * 1024;

export type FileNotice = {
  filename: string;
  message: string;
};

export function checkFiles(files: File[]): { accepted: File[]; notices: FileNotice[] } {
  if (files.length > MAX_FILE_COUNT) {
    return {
      accepted: [],
      notices: [{ filename: '', message: 'The upload has more files than allowed.' }],
    };
  }

  const accepted: File[] = [];
  const notices: FileNotice[] = [];
  for (const file of files) {
    const pdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    if (!pdf) {
      notices.push({ filename: file.name, message: 'The file is not a PDF.' });
    } else if (file.size > MAX_FILE_BYTES) {
      notices.push({ filename: file.name, message: 'The file is over the size limit.' });
    } else {
      accepted.push(file);
    }
  }
  return { accepted, notices };
}
