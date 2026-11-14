import React from "react";
import {
  Folder,
  FileText,
  FileCode,
  FileImage,
  FileVideo,
  FileAudio,
  FileArchive,
  File,
} from "lucide-react";
import type { FileCategory } from "@/types";

interface FileIconProps {
  itemType: "file" | "directory";
  category?: FileCategory;
  extension?: string | null;
  size?: number;
  className?: string;
}

export const FileIcon: React.FC<FileIconProps> = ({
  itemType,
  category,
  extension,
  size = 20,
  className = "",
}) => {
  if (itemType === "directory") {
    return <Folder size={size} className={`text-amber-500 fill-amber-500/20 shrink-0 ${className}`} />;
  }

  const ext = (extension || "").toLowerCase().replace(".", "");

  if (["pdf"].includes(ext)) {
    return <FileText size={size} className={`text-rose-500 shrink-0 ${className}`} />;
  }
  if (["doc", "docx", "odt", "rtf"].includes(ext)) {
    return <FileText size={size} className={`text-blue-500 shrink-0 ${className}`} />;
  }
  if (["xls", "xlsx", "csv"].includes(ext)) {
    return <FileText size={size} className={`text-emerald-500 shrink-0 ${className}`} />;
  }
  if (["ppt", "pptx"].includes(ext)) {
    return <FileText size={size} className={`text-orange-500 shrink-0 ${className}`} />;
  }
  if (["md", "markdown", "txt"].includes(ext)) {
    return <FileText size={size} className={`text-sky-500 shrink-0 ${className}`} />;
  }

  switch (category) {
    case "image":
      return <FileImage size={size} className={`text-sky-500 shrink-0 ${className}`} />;
    case "code":
      return <FileCode size={size} className={`text-emerald-500 shrink-0 ${className}`} />;
    case "video":
      return <FileVideo size={size} className={`text-rose-600 shrink-0 ${className}`} />;
    case "audio":
      return <FileAudio size={size} className={`text-amber-600 shrink-0 ${className}`} />;
    case "archive":
      return <FileArchive size={size} className={`text-amber-700 shrink-0 ${className}`} />;
    case "document":
      return <FileText size={size} className={`text-blue-500 shrink-0 ${className}`} />;
    default:
      return <File size={size} className={`text-slate-400 shrink-0 ${className}`} />;
  }
};
