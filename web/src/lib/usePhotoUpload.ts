import { useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import { uploadMedia } from "../api/generated/sbl";
import { errorText } from "./admin";

/** What the server takes for a post's picture (`uploads.IMAGE_TYPES`). */
export const PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** The pictures among dropped or pasted files — a dropped file skips the chooser's
 *  `accept`, and a clipboard may carry text and a picture at once. */
export function photosIn(files: FileList | null | undefined): File[] {
  return Array.from(files ?? []).filter((file) => PHOTO_TYPES.includes(file.type));
}

export type UploadedPhoto = { url: string; name: string };

/** Picking a picture for a post and uploading it into the library — Stories R-1, R-2. One
 *  hidden file input, a busy flag and the error, for the post's own picture and a picture
 *  in its text alike. A picture the library already holds answers its entry, not a copy.
 *
 *     const photo = usePhotoUpload((url, name) => …);
 *     <Button onPress={photo.pick}>…</Button>
 *     <input {...photo.input} data-testid="…" />
 *
 *  A file that arrives another way — dropped, pasted — goes through `photo.upload(file)`,
 *  which answers where it went, or `null` after showing the error. */
export function usePhotoUpload(onUploaded: (url: string, name: string) => void) {
  const { t } = useTranslation("admin");
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File): Promise<UploadedPhoto | null> => {
    setBusy(true);
    setError(null);
    try {
      const { url, alt } = await uploadMedia({ file });
      return { url, name: alt };
    } catch (e) {
      setError(errorText(e, t("posts.photoError")));
      return null;
    } finally {
      setBusy(false);
    }
  };

  return {
    busy,
    error,
    upload,
    pick: () => ref.current?.click(),
    input: {
      ref,
      type: "file",
      accept: PHOTO_TYPES.join(","),
      className: "hidden",
      onChange: (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        // Cleared, so choosing the same file again uploads it again.
        e.target.value = "";
        if (file) void upload(file).then((done) => done && onUploaded(done.url, done.name));
      },
    },
  };
}
