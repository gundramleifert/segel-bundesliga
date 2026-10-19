import { useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import { uploadPostPhoto } from "../api/generated/sbl";
import { errorText } from "./admin";

/** Picking a picture for a post and uploading it — Story R-1. One hidden file input, a
 *  busy flag and the error, for the post's own picture and a picture in its text alike.
 *
 *     const photo = usePhotoUpload((url, name) => …);
 *     <Button onPress={photo.pick}>…</Button>
 *     <input {...photo.input} data-testid="…" />
 */
export function usePhotoUpload(onUploaded: (url: string, name: string) => void) {
  const { t } = useTranslation("admin");
  const ref = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const { url } = await uploadPostPhoto({ file });
      onUploaded(url, file.name.replace(/\.[^.]+$/, ""));
    } catch (e) {
      setError(errorText(e, t("posts.photoError")));
    } finally {
      setBusy(false);
    }
  };

  return {
    busy,
    error,
    pick: () => ref.current?.click(),
    input: {
      ref,
      type: "file",
      accept: "image/jpeg,image/png",
      className: "hidden",
      onChange: (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        // Cleared, so choosing the same file again uploads it again.
        e.target.value = "";
        if (file) void upload(file);
      },
    },
  };
}
