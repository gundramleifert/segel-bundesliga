import { useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import { uploadMedia } from "../api/generated/sbl";
import type { Media } from "../api/types";
import { errorText } from "./admin";

/** For the file chooser only: it offers pictures first, and on a phone the camera and the
 *  gallery. Never a check — whether a file is a picture is the server's to say, from its
 *  content (`uploads.sniffed`), since a browser names a file's type after its extension. */
export const PHOTO_ACCEPT = "image/*";

/** Every file dropped or pasted, as it is: the server tells a picture by its content, and
 *  a file named wrongly is still a picture. A clipboard with only text carries no file. */
export function filesIn(files: FileList | null | undefined): File[] {
  return Array.from(files ?? []);
}

/** Picking a picture for a post and uploading it into the library — Stories R-1, R-2. One
 *  hidden file input, a busy flag and the error, for the post's own picture and a picture
 *  in its text alike. A picture the library already holds answers its entry, not a copy.
 *
 *     const photo = usePhotoUpload((item) => …);   // the library entry
 *     <Button onPress={photo.pick}>…</Button>
 *     <input {...photo.input} data-testid="…" />
 *
 *  A file that arrives another way — dropped, pasted — goes through `photo.upload(file)`,
 *  which answers the entry, or `null` after showing the error. */
export function usePhotoUpload(onUploaded: (item: Media) => void) {
  const { t } = useTranslation("admin");
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File): Promise<Media | null> => {
    setBusy(true);
    setError(null);
    try {
      return await uploadMedia({ file });
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
      accept: PHOTO_ACCEPT,
      className: "hidden",
      onChange: (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        // Cleared, so choosing the same file again uploads it again.
        e.target.value = "";
        if (file) void upload(file).then((item) => item && onUploaded(item));
      },
    },
  };
}
